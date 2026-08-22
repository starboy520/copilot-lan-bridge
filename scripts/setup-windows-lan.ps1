#Requires -RunAsAdministrator
[CmdletBinding()]
param(
    [string]$Distro = "Ubuntu-24.04",
    [ValidateRange(1, 65535)]
    [int]$Port = 18787,
    [string]$ListenAddress
)

$ErrorActionPreference = "Stop"

$wslAddresses = (& wsl.exe -d $Distro -- hostname -I) -split "\s+" | Where-Object { $_ }
$wslAddress = $wslAddresses | Where-Object { $_ -match "^\d{1,3}(\.\d{1,3}){3}$" } | Select-Object -First 1
if (-not $wslAddress) {
    throw "Could not determine the IPv4 address for WSL distro '$Distro'."
}

if (-not $ListenAddress) {
    $defaultRoute = Get-NetRoute -DestinationPrefix "0.0.0.0/0" |
        Sort-Object RouteMetric, InterfaceMetric |
        Select-Object -First 1
    if (-not $defaultRoute) {
        throw "Could not determine the Windows default network interface."
    }

    $ListenAddress = Get-NetIPAddress -InterfaceIndex $defaultRoute.InterfaceIndex -AddressFamily IPv4 |
        Where-Object { $_.IPAddress -notlike "169.254.*" } |
        Select-Object -ExpandProperty IPAddress -First 1
}
if (-not $ListenAddress) {
    throw "Could not determine the Windows LAN IPv4 address. Pass -ListenAddress explicitly."
}

& netsh.exe interface portproxy delete v4tov4 listenaddress=$ListenAddress listenport=$Port 2>$null | Out-Null
& netsh.exe interface portproxy add v4tov4 listenaddress=$ListenAddress listenport=$Port connectaddress=$wslAddress connectport=$Port
if ($LASTEXITCODE -ne 0) {
    throw "Failed to create the Windows-to-WSL port proxy."
}

$ruleName = "Copilot LAN Bridge (WSL)"
Remove-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
New-NetFirewallRule `
    -DisplayName $ruleName `
    -Direction Inbound `
    -Action Allow `
    -Protocol TCP `
    -LocalAddress $ListenAddress `
    -LocalPort $Port `
    -RemoteAddress LocalSubnet `
    -Profile Any | Out-Null

Write-Host "Copilot LAN Bridge is available at http://${ListenAddress}:${Port}/v1"
Write-Host "Forwarding Windows ${ListenAddress}:${Port} to WSL ${wslAddress}:${Port}"
Write-Host "Firewall access is limited to the local subnet."