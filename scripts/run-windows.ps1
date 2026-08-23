[CmdletBinding()]
param(
    [string]$HostAddress = "0.0.0.0",
    [ValidateRange(1, 65535)]
    [int]$Port = 18787,
    [string]$AuthFile,
    [string]$ConfigDir = (Join-Path $HOME ".config\copilot-lan-bridge"),
    [ValidateRange(1, 3600)]
    [int]$RestartDelaySeconds = 3
)

$ErrorActionPreference = "Stop"

$repoDir = Split-Path -Parent $PSScriptRoot
$bridgeExecutable = Join-Path $repoDir ".venv\Scripts\copilot-lan-bridge.exe"
$keyFile = Join-Path $ConfigDir "api-key"

if (-not (Test-Path -LiteralPath $bridgeExecutable -PathType Leaf)) {
    throw "Bridge executable was not found at '$bridgeExecutable'. Install the project first."
}

New-Item -ItemType Directory -Force -Path $ConfigDir | Out-Null
if (-not (Test-Path -LiteralPath $keyFile -PathType Leaf) -or (Get-Item -LiteralPath $keyFile).Length -eq 0) {
    $keyBytes = New-Object byte[] 32
    $random = [Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $random.GetBytes($keyBytes)
    }
    finally {
        $random.Dispose()
    }
    $bridgeKey = [BitConverter]::ToString($keyBytes).Replace("-", "").ToLowerInvariant()
    [IO.File]::WriteAllText($keyFile, $bridgeKey, [Text.Encoding]::ASCII)
}

$env:COPILOT_BRIDGE_HOST = $HostAddress
$env:COPILOT_BRIDGE_PORT = $Port.ToString()
$env:COPILOT_BRIDGE_API_KEY = [IO.File]::ReadAllText($keyFile).Trim()
if ($AuthFile) {
    $env:OPENCODE_AUTH_FILE = $AuthFile
}

Set-Location $repoDir
while ($true) {
    & $bridgeExecutable
    $exitCode = $LASTEXITCODE
    Write-Error "Copilot LAN Bridge exited with status $exitCode; restarting in $RestartDelaySeconds seconds." -ErrorAction Continue
    Start-Sleep -Seconds $RestartDelaySeconds
}