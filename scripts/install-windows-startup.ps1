#Requires -RunAsAdministrator
[CmdletBinding()]
param(
    [string]$TaskName = "Copilot LAN Bridge"
)

$ErrorActionPreference = "Stop"

$runner = Join-Path $PSScriptRoot "run-windows.ps1"
if (-not (Test-Path -LiteralPath $runner -PathType Leaf)) {
    throw "Runner script was not found at '$runner'."
}

$powerShell = Join-Path $PSHOME "powershell.exe"
if (-not (Test-Path -LiteralPath $powerShell -PathType Leaf)) {
    $powerShell = (Get-Command powershell.exe -ErrorAction Stop).Source
}

$configDir = Join-Path $HOME ".config\copilot-lan-bridge"
$authCandidates = @(
    (Join-Path $HOME ".local\share\opencode\auth.json")
)
if ($env:APPDATA) {
    $authCandidates += Join-Path $env:APPDATA "opencode\auth.json"
}
if ($env:LOCALAPPDATA) {
    $authCandidates += Join-Path $env:LOCALAPPDATA "opencode\auth.json"
}
$authFile = $authCandidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
if (-not $authFile) {
    throw "OpenCode auth.json was not found. Prepare the credential before installing the task."
}

$escapedRunner = $runner.Replace('"', '""')
$escapedConfigDir = $configDir.Replace('"', '""')
$escapedAuthFile = $authFile.Replace('"', '""')
$action = New-ScheduledTaskAction `
    -Execute $powerShell `
    -Argument "-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$escapedRunner`" -ConfigDir `"$escapedConfigDir`" -AuthFile `"$escapedAuthFile`""
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -MultipleInstances IgnoreNew `
    -StartWhenAvailable
$principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType S4U `
    -RunLevel Highest

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Force | Out-Null

Start-ScheduledTask -TaskName $TaskName
Write-Host "Scheduled task '$TaskName' is installed and started."
Write-Host "It starts at boot without an interactive sign-in and restarts automatically after failures."