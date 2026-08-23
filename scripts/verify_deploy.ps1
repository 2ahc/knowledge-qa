# Deployment verification script (ASCII-only output).
# Verifies the compose stack end-to-end through the nginx proxy (port 8090).
param(
    [string]$BaseUrl = "http://localhost:8090",
    [string]$Username = "admin",
    [string]$Password = "admin123"
)

$ErrorActionPreference = "Stop"
$pass = 0
$fail = 0

function Check($name, $cond, $detail) {
    if ($cond) { Write-Host "[PASS] $name"; $script:pass++ }
    else { Write-Host "[FAIL] $name :: $detail"; $script:fail++ }
}

# 1. frontend served
$page = Invoke-WebRequest "$BaseUrl/" -UseBasicParsing -TimeoutSec 10
Check "frontend index" ($page.StatusCode -eq 200 -and $page.Content -match "app") $page.StatusCode

# 2. api health via nginx proxy
$h = Invoke-RestMethod "$BaseUrl/api/health" -TimeoutSec 10
Check "api health via proxy" ($h.status -eq "ok") ($h | ConvertTo-Json -Compress)

# 3. login
$login = Invoke-RestMethod "$BaseUrl/api/auth/login" -Method Post -ContentType "application/json" `
    -Body (@{ username = $Username; password = $Password } | ConvertTo-Json)
Check "login" ($login.access_token.Length -gt 20) "no token"
$hdr = @{ Authorization = "Bearer $($login.access_token)" }

# 4. admin stats
$stats = Invoke-RestMethod "$BaseUrl/api/admin/stats" -Headers $hdr
Check "admin stats" ($stats.user_count -ge 1) ($stats | ConvertTo-Json -Compress)

# 5. create knowledge base (unique name)
$kbName = "deploy-check-" + (Get-Date -Format "HHmmss")
$kb = Invoke-RestMethod "$BaseUrl/api/kbs" -Method Post -ContentType "application/json" -Headers $hdr `
    -Body (@{ name = $kbName; description = "deployment check"; visibility = "private" } | ConvertTo-Json)
Check "create kb" ($kb.id.Length -gt 10) "no kb id"

# 6. upload a small txt document (multipart)
$sample = "The sky is blue. Water is transparent. Shiguang Chayu was founded in 2020."
$boundary = [System.Guid]::NewGuid().ToString()
$LF = "`r`n"
$bodyStr = ("--$boundary$LF" +
    "Content-Disposition: form-data; name=`"file`"; filename=`"deploy-check.txt`"$LF" +
    "Content-Type: text/plain$LF$LF" +
    "$sample$LF" +
    "--$boundary--$LF$LF")
$bytes = [System.Text.Encoding]::UTF8.GetBytes($bodyStr)
$doc = Invoke-RestMethod "$BaseUrl/api/kbs/$($kb.id)/documents" -Method Post -Headers $hdr `
    -ContentType "multipart/form-data; boundary=$boundary" -Body $bytes
Check "upload document" ($doc.id.Length -gt 10) ($doc | ConvertTo-Json -Compress)

# 7. chat against the (empty) kb -> expect graceful fallback (no LLM needed).
# PS 5.1 Invoke-WebRequest breaks on chunked SSE; use HttpWebRequest directly.
$chatPayload = @{ question = "What color is the sky?"; kb_ids = @($kb.id) } | ConvertTo-Json
try {
    $req = [System.Net.HttpWebRequest]::Create("$BaseUrl/api/chat")
    $req.Method = "POST"
    $req.ContentType = "application/json"
    $req.Timeout = 90000
    $req.ReadWriteTimeout = 90000
    $req.Headers.Add("Authorization", "Bearer $($login.access_token)")
    $reqBytes = [System.Text.Encoding]::UTF8.GetBytes($chatPayload)
    $req.ContentLength = $reqBytes.Length
    $reqStream = $req.GetRequestStream()
    $reqStream.Write($reqBytes, 0, $reqBytes.Length)
    $reqStream.Close()
    $resp = $req.GetResponse()
    $reader = New-Object System.IO.StreamReader($resp.GetResponseStream())
    $sseBody = $reader.ReadToEnd()
    $reader.Close()
    $resp.Close()
    $events = ($sseBody -split "`n`n") | Where-Object { $_ -match "^data: " } |
        ForEach-Object { ($_ -replace "^data: ", "") | ConvertFrom-Json }
    $hasDone = ($events | Where-Object { $_.type -eq "done" }).Count -ge 1
    Check "chat SSE stream completes" $hasDone ($sseBody.Substring(0, [Math]::Min(200, $sseBody.Length)))
} catch {
    Check "chat SSE stream completes" $false $_.Exception.Message
}

# 8. conversations persisted
$convs = Invoke-RestMethod "$BaseUrl/api/conversations" -Headers $hdr
Check "conversation persisted" ($convs.Count -ge 1) ($convs | ConvertTo-Json -Compress -Depth 3)

# 9. cleanup: delete check kb (HttpWebRequest; PS 5.1 IWR breaks on 204)
try {
    $delReq = [System.Net.HttpWebRequest]::Create("$BaseUrl/api/kbs/$($kb.id)")
    $delReq.Method = "DELETE"
    $delReq.Headers.Add("Authorization", "Bearer $($login.access_token)")
    $delReq.Timeout = 30000
    $delResp = $delReq.GetResponse()
    $delResp.Close()
    Check "delete kb" $true ""
} catch {
    Check "delete kb" $false $_.Exception.Message
}

Write-Host ""
Write-Host "RESULT: $pass passed, $fail failed"
exit $fail
