Param(
  [switch]$Force
)

$ErrorActionPreference = 'Stop'

function Ensure-Admin {
  if (-not ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host 'Elevating to Administrator...'
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = (Get-Command powershell).Source
    $args = @('-NoProfile','-ExecutionPolicy','Bypass','-File',"$PSCommandPath")
    if ($Force) { $args += '-Force' }
    $psi.Arguments = ($args -join ' ')
    $psi.Verb = 'runas'
    [System.Diagnostics.Process]::Start($psi) | Out-Null
    exit 0
  }
}

function Has-Cmd { param([string]$Name) try { $null = Get-Command $Name -ErrorAction Stop; return $true } catch { return $false } }

Ensure-Admin

Write-Host 'Trying to install Npcap + Nmap via winget...'
if (Has-Cmd winget) {
  try {
    winget install -e --id Nmap.Npcap --silent --accept-source-agreements --accept-package-agreements -h 0
  } catch { Write-Warning "Npcap install via winget failed: $($_.Exception.Message)" }
  try {
    winget install -e --id Insecure.Nmap --silent --accept-source-agreements --accept-package-agreements -h 0
  } catch { Write-Warning "Nmap install via winget failed: $($_.Exception.Message)" }
} else {
  Write-Warning 'winget not found. Trying Chocolatey...'
  if (-not (Has-Cmd choco)) {
    Set-ExecutionPolicy Bypass -Scope Process -Force
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
  }
  choco install -y npcap nmap
}

# Ensure nmap in PATH for current session
$paths = @('C:\Program Files (x86)\Nmap','C:\Program Files\Nmap')
foreach ($p in $paths) {
  if (Test-Path $p) { $env:Path = "$p;" + $env:Path }
}

Write-Host 'Checking nmap availability...'
if (Has-Cmd nmap) {
  nmap --version | Select-Object -First 1 | Write-Host
  Write-Host 'Nmap is installed.'
  exit 0
} else {
  Write-Warning 'Nmap not found after installation. You may need to reopen your terminal.'
  exit 1
}

