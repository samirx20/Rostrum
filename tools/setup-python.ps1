<#
.SYNOPSIS
  Makes (or refreshes) the one Python environment every Rostrum app runs in: C:\Users\Sam\.rostrum\venv by default.
  The shared layer and the apps' Python packages are installed "editable" from this checkout, so code changes show
  up without reinstalling. Safe to run again (only what is missing or changed is installed).

  pwsh -File tools\setup-python.ps1
#>
param(
    [string]$Repo = (Split-Path $PSScriptRoot -Parent),
    [string]$Venv = (Join-Path $HOME ".rostrum\venv")
)
$ErrorActionPreference = "Stop"

function Fail([string]$msg) { Write-Host $msg -ForegroundColor Red; exit 1 }

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Fail "Can't make the Python environment: the 'uv' tool is not installed. Install it from https://docs.astral.sh/uv/ and run this again."
}
$py = Join-Path $Venv "Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Host "Making the Python environment in $Venv ..."
    uv venv --python 3.12 $Venv
    if ($LASTEXITCODE -ne 0) { Fail "Could not make the Python environment in $Venv (see the lines above)." }
}

# What the three apps' screens, scripts and MCP servers need. Left out on purpose: the big optional AI extras
# (2D lip sync, Sound cleanup); install those into the same environment when you want them.
$packages = @(
    "shared\core[mcp]", "shared\gui-kit", "shared\painting-kit",
    "apps\2d\python[mcp,io,render3d]", "apps\sound\python[listen,mcp]", "apps\3d\python[mcp]"
)
$args_ = @("pip", "install", "--python", $py)
foreach ($p in $packages) { $args_ += @("-e", (Join-Path $Repo $p)) }
Write-Host "Installing Rostrum's Python packages from $Repo ..."
& uv @args_
if ($LASTEXITCODE -ne 0) { Fail "Installing Rostrum's Python packages into $Venv failed (see the lines above)." }
Write-Host "Python environment ready: $Venv" -ForegroundColor Green
