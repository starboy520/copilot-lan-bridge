$ErrorActionPreference = "Stop"
$appDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $appDir

if (-not (Test-Path -LiteralPath (Join-Path $appDir "web\index.html"))) {
    Write-Host "Web files are missing. Please build the app first (see README.md)." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

if (-not $env:COPILOT_BRIDGE_API_KEY) {
    try {
        $detectedKey = (& wsl.exe -d Ubuntu --exec bash -lc "test -s ~/.config/copilot-lan-bridge/api-key && cat ~/.config/copilot-lan-bridge/api-key" 2>$null).Trim()
        if ($detectedKey) {
            $env:COPILOT_BRIDGE_API_KEY = $detectedKey
        }
    } catch {
        # The server will display an offline state if the key cannot be found.
    }
}

$env:STUDY_AGENT_HOST = "0.0.0.0"
$env:STUDY_AGENT_PORT = "8765"

$addresses = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" } |
    Select-Object -ExpandProperty IPAddress -Unique

Write-Host ""
Write-Host "Study Agent is starting" -ForegroundColor Green
Write-Host "This computer: http://127.0.0.1:8765"
foreach ($address in $addresses) {
    Write-Host "Phone on the same Wi-Fi: http://${address}:8765"
}
Write-Host "Close this window to stop the service." -ForegroundColor DarkGray
Write-Host ""

$openBrowser = Start-Job -ScriptBlock {
    Start-Sleep -Milliseconds 1200
    Start-Process "http://127.0.0.1:8765"
}
py -3.10 -m server.app --host 0.0.0.0 --port 8765
Remove-Job -Job $openBrowser -Force -ErrorAction SilentlyContinue
