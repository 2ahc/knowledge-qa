$ErrorActionPreference = 'Stop'
Start-Sleep -Seconds 6

$base = 'http://127.0.0.1:8000/api'

$h = Invoke-RestMethod "$base/health"
Write-Output ("health: " + $h.status)

$loginBody = @{ username = 'admin'; password = 'admin123' } | ConvertTo-Json
$tok = Invoke-RestMethod "$base/auth/login" -Method Post -ContentType 'application/json' -Body $loginBody
$auth = @{ Authorization = "Bearer $($tok.access_token)" }
Write-Output "login ok"

$kbBody = @{ name = 'smoke-kb'; description = 'smoke test'; visibility = 'private' } | ConvertTo-Json
$kb = Invoke-RestMethod "$base/kbs" -Method Post -Headers $auth -ContentType 'application/json; charset=utf-8' -Body ([System.Text.Encoding]::UTF8.GetBytes($kbBody))
Write-Output ("kb created: " + $kb.id)

$sample = 'D:\deepseek harness\knowledge-qa\scripts\_smoke_sample.txt'
$docUrl = '{0}/kbs/{1}/documents' -f $base, $kb.id

# multipart upload built by hand (compatible with Windows PowerShell 5.1)
$boundary = [System.Guid]::NewGuid().ToString()
$LF = "`r`n"
$enc = [System.Text.Encoding]::UTF8
$fileBytes = [System.IO.File]::ReadAllBytes($sample)
$header = "Content-Disposition: form-data; name=`"file`"; filename=`"kqa-smoke.txt`"$LF" + "Content-Type: text/plain$LF$LF"
$bodyStart = $enc.GetBytes("--$boundary$LF$header")
$bodyEnd = $enc.GetBytes("$LF--$boundary--$LF")
$body = New-Object byte[] ($bodyStart.Length + $fileBytes.Length + $bodyEnd.Length)
[Array]::Copy($bodyStart, 0, $body, 0, $bodyStart.Length)
[Array]::Copy($fileBytes, 0, $body, $bodyStart.Length, $fileBytes.Length)
[Array]::Copy($bodyEnd, 0, $body, $bodyStart.Length + $fileBytes.Length, $bodyEnd.Length)
$doc = Invoke-RestMethod $docUrl -Method Post -Headers $auth -ContentType "multipart/form-data; boundary=$boundary" -Body $body
Write-Output ("uploaded doc: " + $doc.id + " status=" + $doc.status)

$docs = $null
for ($i = 0; $i -lt 45; $i++) {
    Start-Sleep -Seconds 2
    $docs = Invoke-RestMethod $docUrl -Headers $auth
    $status = $docs[0].status
    Write-Output ("  ... status: " + $status)
    if ($status -eq 'done' -or $status -eq 'failed') { break }
}
Write-Output ("final status: " + $docs[0].status + " chunks=" + $docs[0].chunk_count)
if ($docs[0].error) { Write-Output ("error: " + $docs[0].error) }
