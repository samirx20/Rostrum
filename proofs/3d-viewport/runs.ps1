# All the proof's measured runs, one process each, every one through the GPU lock, in a background window.
#   pwsh -File proofs\3d-viewport\runs.ps1 <result folder> [run names...]
param([string]$Out = "$env:USERPROFILE\.rostrum\waves\results\3d-pview", [string[]]$Only = @())
$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot
$env:ROSTRUM_BACKGROUND_WINDOWS = '1'
$runs = [ordered]@{
  'sculpt-medium'      = @('--mode', 'sculpt', '--brush', 'medium')
  'sculpt-quarter'     = @('--mode', 'sculpt', '--brush', 'quarter')
  'head-medium'        = @('--mode', 'sculpt', '--brush', 'medium', '--clay', 'head')
  'head-quarter'       = @('--mode', 'sculpt', '--brush', 'quarter', '--clay', 'head')
  'head-medium-nofinish' = @('--mode', 'sculpt', '--brush', 'medium', '--clay', 'head', '--no-finish')
  'sculpt-medium-tick' = @('--mode', 'sculpt', '--brush', 'medium')  # PVIEW_TICK=1: waits for Qt's frame tick
  'sculpt-medium-basic' = @('--mode', 'sculpt', '--brush', 'medium', '--loop', 'basic')  # Qt's one-thread loop
  'sculpt-medium-vsync' = @('--mode', 'sculpt', '--brush', 'medium', '--vsync', '1')  # waits for the display
  'orbit-300'          = @('--mode', 'orbit', '--items', '300', '--moves', '300')
  'orbit-300-fast'     = @('--mode', 'orbit', '--items', '300', '--moves', '600', '--interval', '1')
}
New-Item -ItemType Directory -Force $Out | Out-Null
foreach ($name in $runs.Keys) {
  if ($Only.Count -and $name -notin $Only) { continue }
  $env:PVIEW_TICK = if ($name -like '*-tick') { '1' } else { '' }
  $dir = Join-Path $Out $name
  $log = Join-Path $Out "$name.log"
  pwsh -File "$env:USERPROFILE\.rostrum\waves\heavy.ps1" run "priyam: pview $name" gpu cmd.exe /c "$here\run.bat" @($runs[$name]) --out $dir *> $log
  $code = $LASTEXITCODE
  $line = Get-Content $log | Where-Object { $_ -match 'move->screen' } | Select-Object -Last 1
  Write-Output "$name (exit $code): $line"
}
