# P-3D-2: render a USD stage through Hydra -> Cycles (the H1 build), measuring time, peak RAM and VRAM.
# Fails loudly: missing stage, non-zero exit, no output, or any shader-graph warning from the delegate.
# pwsh -File C:\Users\Sam\.rostrum\waves\heavy.ps1 run "hem: render" gpu pwsh -File <this> <stage.usda> <out.exr> [samples] [width] [height]
param([string]$Stage, [string]$Out, [int]$Samples = 64, [int]$Width = 960, [int]$Height = 540)
$ErrorActionPreference = "Stop"
$exe = Join-Path $PSScriptRoot "..\3d-product\.build\cycles\install\cycles.exe"
if (-not (Test-Path $Stage)) { Write-Error "stage not found: $Stage"; exit 1 }
if (-not (Test-Path $exe)) { Write-Error "Cycles build not found: $exe (see proofs\3d-product\README.md)"; exit 1 }
$log = [IO.Path]::ChangeExtension($Out, ".log")
if (Test-Path $Out) { Remove-Item $Out }
$env:OCIO = "ocio://cg-config-latest"   # colour management on: Cycles renders in ACEScg, textures converted by OCIO
$vram0 = [int](nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits)
$argv = "--background --device OPTIX --samples $Samples --denoise --width $Width --height $Height --output `"$Out`" `"$Stage`""
$sw = [Diagnostics.Stopwatch]::StartNew()
$p = Start-Process -FilePath $exe -ArgumentList $argv -PassThru -NoNewWindow -RedirectStandardOutput $log -RedirectStandardError "$log.err"
$peakV = $vram0; $peakRam = 0
while (-not $p.HasExited) {
  $v = [int](nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits); if ($v -gt $peakV) { $peakV = $v }
  try { $p.Refresh(); if ($p.PeakWorkingSet64 -gt $peakRam) { $peakRam = $p.PeakWorkingSet64 } } catch {}
  Start-Sleep -Milliseconds 500
}
$p.WaitForExit(); $sw.Stop()
$summary = "stage=$Stage samples=$Samples size=${Width}x$Height exit=$($p.ExitCode) seconds=$([math]::Round($sw.Elapsed.TotalSeconds,1)) peakRAM_MB=$([math]::Round($peakRam/1MB)) VRAM_before_MB=$vram0 VRAM_peak_MB=$peakV"
$summary | Tee-Object -FilePath ([IO.Path]::ChangeExtension($Out, ".stats.txt"))
$warn = Select-String -Path $log, "$log.err" -Pattern "Could not|Ignoring|Unsupported|Runtime Error|Warning: in" -ErrorAction SilentlyContinue
if ($warn) { $warn | ForEach-Object { $_.Line }; Write-Error "delegate reported shader/scene problems (above)"; exit 2 }
if ($p.ExitCode -ne 0 -or -not (Test-Path $Out)) { Get-Content "$log.err" -Tail 20; Write-Error "render failed: $Out"; exit 1 }
