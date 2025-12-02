Param(
  [switch]$Recreate,
  [switch]$SetDns
)

$ErrorActionPreference = 'Stop'

function Ensure-File {
  param([string]$Path,[string]$Content)
  if (!(Test-Path $Path)) {
    New-Item -ItemType Directory -Force -Path ([System.IO.Path]::GetDirectoryName($Path)) | Out-Null
    Set-Content -Path $Path -Value $Content -Encoding UTF8
  }
}

# Paths relative to repo root
$repoRoot = (Resolve-Path "$PSScriptRoot\..\..\..\").Path
$genFile = Join-Path $repoRoot 'back\generated\dns\dnsmasq_blocklist.conf'
$composeDir = (Resolve-Path $PSScriptRoot).Path

Ensure-File -Path $genFile -Content '# empty blocklist`n'

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  Write-Error 'Docker not found. Install Docker Desktop and retry.'
}

# Verify Docker engine is running; try to start Docker Desktop if not
$engineOk = $false
try {
  docker info | Out-Null
  $engineOk = $true
} catch {
  $engineOk = $false
}

if (-not $engineOk) {
  $pf = $Env:ProgramFiles
  $pf86 = [Environment]::GetEnvironmentVariable('ProgramFiles(x86)')
  $paths = @()
  if ($pf)  { $paths += (Join-Path -Path $pf  -ChildPath 'Docker\Docker\Docker Desktop.exe') }
  if ($pf86) { $paths += (Join-Path -Path $pf86 -ChildPath 'Docker\Docker\Docker Desktop.exe') }

  foreach ($p in $paths) {
    if (Test-Path $p) {
      Write-Host "Starting Docker Desktop: $p"
      Start-Process -FilePath $p | Out-Null
      break
    }
  }
  # wait up to ~2 minutes for engine
  for ($i=0; $i -lt 60; $i++) {
    Start-Sleep -Seconds 2
    try {
      docker info | Out-Null
      $engineOk = $true
      break
    } catch {}
  }
  if (-not $engineOk) {
    Write-Error 'Docker engine not available. Please start Docker Desktop and retry.'
    exit 2
  }
}

Push-Location $composeDir
try {
  if ($Recreate) {
    docker compose down --remove-orphans | Out-Null
  }
  docker compose up -d
  if ($LASTEXITCODE -ne 0) {
    throw 'docker compose up failed.'
  }
  Write-Host 'dnsmasq is running in Docker and listening on 127.0.0.1:53.'
  if ($SetDns) {
    try {
      $isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
      if (-not $isAdmin) {
        Write-Warning 'Automatic DNS change requires Administrator. Re-run PowerShell as Administrator.'
      } else {
        $iface = (Get-NetAdapter | Where-Object Status -eq Up | Sort-Object ifIndex | Select-Object -First 1 -ExpandProperty Name)
        if ($null -ne $iface) {
          Set-DnsClientServerAddress -InterfaceAlias $iface -ServerAddresses 127.0.0.1 -ErrorAction Stop
          Write-Host "DNS of interface '$iface' set to 127.0.0.1"
        } else {
          Write-Warning 'No active network interface detected to set DNS.'
        }
      }
    } catch {
      Write-Warning "Automatic DNS configuration failed: $($_.Exception.Message)"
    }
    Write-Host "To restore auto-DNS: back/tools/dns/reset_dns_windows.ps1"
  } else {
    Write-Host 'Set your system DNS to 127.0.0.1 to use dnsmasq.'
  }
}
finally {
  Pop-Location
}
