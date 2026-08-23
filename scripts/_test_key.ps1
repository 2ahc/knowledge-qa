$ErrorActionPreference = 'Stop'
$key = ((Get-Content 'C:\Users\16412\.bailian\config.json' -Raw | ConvertFrom-Json).api_key)
$ws = ((Get-Content 'C:\Users\16412\.bailian\config.json' -Raw | ConvertFrom-Json).workspace_id)
$body = '{"model":"text-embedding-v4","input":{"texts":["测试"]},"parameters":{}}'
$url = 'https://dashscope.aliyuncs.com/api/v1/services/embeddings/text-embedding/text-embedding'

Write-Output "--- Test 1: native endpoint, no workspace header ---"
try {
    $r = Invoke-RestMethod $url -Method Post -ContentType 'application/json' -Headers @{ Authorization = "Bearer $key" } -Body ([System.Text.Encoding]::UTF8.GetBytes($body))
    Write-Output ("OK, dim=" + $r.output.embeddings[0].embedding.Count)
} catch {
    Write-Output ("FAIL: " + $_.Exception.Message)
    if ($_.ErrorDetails) { Write-Output ($_.ErrorDetails.Message) }
}

Write-Output "--- Test 2: native endpoint WITH workspace header ---"
try {
    $r = Invoke-RestMethod $url -Method Post -ContentType 'application/json' -Headers @{ Authorization = "Bearer $key"; 'X-DashScope-WorkSpace' = $ws } -Body ([System.Text.Encoding]::UTF8.GetBytes($body))
    Write-Output ("OK, dim=" + $r.output.embeddings[0].embedding.Count)
} catch {
    Write-Output ("FAIL: " + $_.Exception.Message)
    if ($_.ErrorDetails) { Write-Output ($_.ErrorDetails.Message) }
}

Write-Output "--- Test 3: OpenAI-compatible endpoint WITH workspace header ---"
try {
    $body2 = '{"model":"text-embedding-v4","input":["测试"]}'
    $r = Invoke-RestMethod 'https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings' -Method Post -ContentType 'application/json' -Headers @{ Authorization = "Bearer $key"; 'X-DashScope-WorkSpace' = $ws } -Body ([System.Text.Encoding]::UTF8.GetBytes($body2))
    Write-Output ("OK, dim=" + $r.data[0].embedding.Count)
} catch {
    Write-Output ("FAIL: " + $_.Exception.Message)
    if ($_.ErrorDetails) { Write-Output ($_.ErrorDetails.Message) }
}
