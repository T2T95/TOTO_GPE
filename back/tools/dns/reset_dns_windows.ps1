Param(
  [string]$Interface
)

$ErrorActionPreference = 'Stop'

if (-not ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  Write-Warning 'Run this script as Administrator.'
}

if (-not $Interface) {
  $Interface = (Get-NetAdapter | Where-Object Status -eq Up | Sort-Object ifIndex | Select-Object -First 1 -ExpandProperty Name)
}

if (-not $Interface) {
  Write-Error 'No active interface detected.'
}

Set-DnsClientServerAddress -InterfaceAlias $Interface -ResetServerAddresses
Write-Host "DNS of interface '$Interface' restored to automatic."

