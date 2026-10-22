<#
.SYNOPSIS
  Builds RostrumSetup-<version>.exe: the bundle (tools\release\bundle.py), then Inno Setup packs it.
  Runs through the machine's job lock (a build slot) when heavy.ps1 is there.

  pwsh -File tools\release\build-installer.ps1 -Out <folder> [-Version <must match VERSION>] [-Engines <checkout with built engines>]

  Needs (build machine only, never the person installing): uv, a Python with Pillow (C:\Users\Sam\.rostrum\venv by
  default), python.org's embeddable Python zip and Inno Setup 6 in C:\Users\Sam\.rostrum\release-cache.
#>
param(
    [Parameter(Mandatory)][string]$Out,
    [string]$Version = (Get-Content (Join-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) "VERSION") -TotalCount 1).Trim(),
    [string]$Engines = (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent),
    [string]$Python = (Join-Path $HOME ".rostrum\venv\Scripts\python.exe"),
    [string]$Iscc = (Join-Path $HOME ".rostrum\release-cache\tools\innosetup6\ISCC.exe")
)
$ErrorActionPreference = "Stop"
foreach ($f in @($Python, $Iscc)) { if (-not (Test-Path $f)) { Write-Host "FAIL: $f is missing" -ForegroundColor Red; exit 1 } }
$file = (Get-Content (Join-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) "VERSION") -TotalCount 1).Trim()
if ($Version -ne $file) { Write-Host "FAIL: -Version $Version is not the repo's VERSION ($file); change VERSION instead" -ForegroundColor Red; exit 1 }
$work = Join-Path $HOME ".rostrum\release-cache\build-$Version"
$heavy = Join-Path $HOME ".rostrum\waves\heavy.ps1"
New-Item -ItemType Directory -Force $Out | Out-Null

$label = "sam: Rostrum installer $Version"
if (Test-Path $heavy) { & pwsh -NoProfile -File $heavy acquire $label build; if ($LASTEXITCODE) { exit 1 } }
try {
    & $Python (Join-Path $PSScriptRoot "bundle.py") --out $work --engines $Engines
    if ($LASTEXITCODE) { throw "the bundle failed (lines above)" }
    $t = Measure-Command { & $Iscc /Q "/DStage=$work\stage" "/DOutDir=$Out" "/DVersion=$Version" (Join-Path $PSScriptRoot "rostrum.iss") }
    if ($LASTEXITCODE) { throw "Inno Setup failed (lines above)" }
} catch {
    Write-Host "FAIL: building the installer: $_" -ForegroundColor Red; exit 1
} finally {
    if (Test-Path $heavy) { & pwsh -NoProfile -File $heavy release $label }
}
$exe = Join-Path $Out "RostrumSetup-$Version.exe"
Write-Host ("Installer ready: {0} ({1:N0} MB, packed in {2:N0} s)" -f $exe, ((Get-Item $exe).Length / 1MB), $t.TotalSeconds) -ForegroundColor Green
