# Full end-to-end acceptance: login -> create kb -> upload doc -> index ->
# streaming chat with citations (2 turns) -> eval run with metrics.
# ASCII-only script (Chinese strings loaded from files). PS 5.1 compatible.
param([string]$BaseUrl = "http://localhost:8090")

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pass = 0; $fail = 0
function Check($name, $cond, $detail) {
    if ($cond) { Write-Host "[PASS] $name"; $script:pass++ }
    else { Write-Host "[FAIL] $name :: $detail"; $script:fail++ }
}

function SsePost($url, $token, $json, $timeoutSec) {
    $req = [System.Net.HttpWebRequest]::Create($url)
    $req.Method = "POST"
    $req.ContentType = "application/json"
    $req.Timeout = $timeoutSec * 1000
    $req.ReadWriteTimeout = $timeoutSec * 1000
    $req.Headers.Add("Authorization", "Bearer $token")
    $b = [System.Text.Encoding]::UTF8.GetBytes($json)
    $req.ContentLength = $b.Length
    $s = $req.GetRequestStream(); $s.Write($b, 0, $b.Length); $s.Close()
    try {
        $resp = $req.GetResponse()
    } catch [System.Net.WebException] {
        $errBody = ""
        try {
            $er = $_.Exception.Response
            if ($er) { $errBody = (New-Object System.IO.StreamReader($er.GetResponseStream())).ReadToEnd() }
        } catch {}
        throw "HTTP error on $url : $errBody"
    }
    $reader = New-Object System.IO.StreamReader($resp.GetResponseStream())
    $body = $reader.ReadToEnd()
    $reader.Close(); $resp.Close()
    return $body
}

# ---- 1. login ----
$login = Invoke-RestMethod "$BaseUrl/api/auth/login" -Method Post -ContentType "application/json" `
    -Body '{"username":"admin","password":"admin123"}'
$token = $login.access_token
$hdr = @{ Authorization = "Bearer $token" }
Check "login" ($token.Length -gt 20) "no token"

# ---- 2. create kb ----
$kbName = "e2e-acceptance-" + (Get-Date -Format "HHmmss")
$kb = Invoke-RestMethod "$BaseUrl/api/kbs" -Method Post -ContentType "application/json" -Headers $hdr `
    -Body (@{ name = $kbName; description = "e2e acceptance"; visibility = "private" } | ConvertTo-Json)
Check "create kb" ($kb.id.Length -gt 10) "no kb id"

# ---- 3. upload document (multipart from file bytes) ----
$fileBytes = [System.IO.File]::ReadAllBytes((Join-Path $scriptDir "_e2e_doc.md"))
$boundary = [System.Guid]::NewGuid().ToString()
$LF = "`r`n"
$head = [System.Text.Encoding]::UTF8.GetBytes(
    "--$boundary$LF" +
    "Content-Disposition: form-data; name=`"file`"; filename=`"_e2e_doc.md`"$LF" +
    "Content-Type: text/markdown$LF$LF")
$tail = [System.Text.Encoding]::UTF8.GetBytes("$LF--$boundary--$LF")
$bodyBytes = New-Object byte[] ($head.Length + $fileBytes.Length + $tail.Length)
[Array]::Copy($head, 0, $bodyBytes, 0, $head.Length)
[Array]::Copy($fileBytes, 0, $bodyBytes, $head.Length, $fileBytes.Length)
[Array]::Copy($tail, 0, $bodyBytes, $head.Length + $fileBytes.Length, $tail.Length)
$doc = Invoke-RestMethod "$BaseUrl/api/kbs/$($kb.id)/documents" -Method Post -Headers $hdr `
    -ContentType "multipart/form-data; boundary=$boundary" -Body $bodyBytes
Check "upload document" ($doc.id.Length -gt 10) ($doc | ConvertTo-Json -Compress)

# ---- 4. poll indexing until done (embed + chunk via real models) ----
$indexed = $false
for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Seconds 3
    $docs = Invoke-RestMethod "$BaseUrl/api/kbs/$($kb.id)/documents" -Headers $hdr
    $d = $docs | Where-Object { $_.id -eq $doc.id }
    if ($d.status -eq "done") { $indexed = $true; break }
    if ($d.status -eq "failed") { break }
}
Check "document indexed (real embedding)" ($indexed -and $d.chunk_count -gt 0) "status=$($d.status) chunks=$($d.chunk_count) err=$($d.error)"

# ---- 5. streaming chat turn 1, expect answer + citations ----
$questions = @(Get-Content (Join-Path $scriptDir "_e2e_questions.txt") -Encoding UTF8 | Where-Object { $_.Trim() } | ForEach-Object { [string]$_ })
$q1 = [string]$questions[0]
# NOTE: PS 5.1 ConvertTo-Json unwraps single-element arrays -> build JSON manually
$q1Json = ConvertTo-Json $q1
$chatBody1 = "{`"question`": $q1Json, `"kb_ids`": [`"$($kb.id)`"]}"
$sse = SsePost "$BaseUrl/api/chat" $token $chatBody1 120
$events = ($sse -split "`n`n") | Where-Object { $_ -match "^data: " } |
    ForEach-Object { ($_ -replace "^data: ", "") | ConvertFrom-Json }
$answer1 = (($events | Where-Object { $_.type -eq "token" }).content) -join ""
$cites = ($events | Where-Object { $_.type -eq "citations" }).citations
$doneEv = $events | Where-Object { $_.type -eq "done" }
Check "chat turn1 streams done" ($null -ne $doneEv) ($sse.Substring(0, [Math]::Min(150, $sse.Length)))
Check "chat turn1 answer correct (2020 + city)" ($answer1 -match "2020") $answer1
Check "chat turn1 has citations" ($cites.Count -ge 1) "no citations event"
if ($cites.Count -ge 1) {
    Check "citation points to uploaded doc" ($cites[0].filename -like "*_e2e_doc*") ($cites[0].filename)
    Check "citation has content snippet" ($cites[0].content.Length -gt 20) "empty snippet"
}

# ---- 6. multi-turn: follow-up in same conversation ----
$convId = $doneEv.conversation_id
$q2Json = ConvertTo-Json ([string]$questions[1])
$chatBody2 = "{`"question`": $q2Json, `"kb_ids`": [`"$($kb.id)`"], `"conversation_id`": `"$convId`"}"
$sse2 = SsePost "$BaseUrl/api/chat" $token $chatBody2 120
$events2 = ($sse2 -split "`n`n") | Where-Object { $_ -match "^data: " } |
    ForEach-Object { ($_ -replace "^data: ", "") | ConvertFrom-Json }
$answer2 = (($events2 | Where-Object { $_.type -eq "token" }).content) -join ""
Check "chat turn2 multi-turn works" ($answer2.Length -gt 20) $answer2

# ---- 7. eval: dataset + run + metrics ----
$evalItems = @()
Get-Content (Join-Path $scriptDir "_e2e_eval.jsonl") -Encoding UTF8 | ForEach-Object {
    if ($_.Trim()) { $evalItems += (ConvertFrom-Json $_) }
}
$dsJson = @{ name = "e2e-acceptance"; items = $evalItems } | ConvertTo-Json -Depth 5
$ds = Invoke-RestMethod "$BaseUrl/api/eval/datasets" -Method Post -ContentType "application/json" -Headers $hdr -Body ([System.Text.Encoding]::UTF8.GetBytes($dsJson))
Check "eval dataset created" ($ds.id.Length -gt 10) ($ds | ConvertTo-Json -Compress)

$runBody = "{`"dataset_id`": `"$($ds.id)`", `"kb_ids`": [`"$($kb.id)`"]}"
$run = Invoke-RestMethod "$BaseUrl/api/eval/runs" -Method Post -ContentType "application/json" -Headers $hdr -Body ([System.Text.Encoding]::UTF8.GetBytes($runBody))
Check "eval run queued" ($run.id.Length -gt 10) ($run | ConvertTo-Json -Compress)

$finished = $false
for ($i = 0; $i -lt 90; $i++) {
    Start-Sleep -Seconds 4
    $runs = Invoke-RestMethod "$BaseUrl/api/eval/runs" -Headers $hdr
    $r = $runs | Where-Object { $_.id -eq $run.id }
    if ($r.status -in "done", "failed") { $finished = $true; break }
}
Check "eval run finished" ($finished -and $r.status -eq "done") "status=$($r.status) err=$($r.error)"
$detail = Invoke-RestMethod "$BaseUrl/api/eval/runs/$($run.id)" -Headers $hdr
$m = $detail.metrics
Write-Host ("eval metrics: hit={0} kw={1} faith={2} relev={3} total={4}" -f $m.retrieval_precision, $m.avg_keyword_rate, $m.avg_faithfulness, $m.avg_relevance, $m.total)
Check "eval retrieval precision >= 0.99" ($m.retrieval_precision -ge 0.99) ($m | ConvertTo-Json -Compress)
Check "eval faithfulness >= 4" ($m.avg_faithfulness -ge 4) ($m | ConvertTo-Json -Compress)

# ---- 8. admin stats reflect activity ----
$stats = Invoke-RestMethod "$BaseUrl/api/admin/stats" -Headers $hdr
Check "admin stats show questions" ($stats.question_count -ge 2) ($stats | ConvertTo-Json -Compress)

Write-Host ""
Write-Host "E2E RESULT: $pass passed, $fail failed"
exit $fail
