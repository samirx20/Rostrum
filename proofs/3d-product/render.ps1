# P-3D-1: render a USD stage through Hydra -> Cycles, measuring time, peak RAM and peak VRAM.
# pwsh -File C:\Users\Sam\.rostrum\waves\heavy.ps1 run "hem: render" gpu pwsh -File C:\Users\Sam\.t3\worktrees\Rostrum\team-hem\proofs\3d-product\render.ps1 <stage.usda> <out.exr> [samples] [device] [width] [height]
param([string]$Stage, [string]$Out, [int]$Samples = 256, [string]$Device = "OPTIX", [int]$Width = 1920, [int]$Height = 1080)
$exe = Join-Path $PSScriptRoot ".build\cycles\install\cycles.exe"
$log = [IO.Path]::ChangeExtension($Out, ".log")
if (Test-Path $Out) { Remove-Item $Out }
$vram0 = [int](nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits)
$argv = "--background --device $Device --samples $Samples --denoise --width $Width --height $Height --output `"$Out`" `"$Stage`""
$sw = [Diagnostics.Stopwatch]::StartNew()
$p = Start-Process -FilePath $exe -ArgumentList $argv -PassThru -NoNewWindow -RedirectStandardOutput $log -RedirectStandardError "$log.err"
$peakV = $vram0; $peakRam = 0
while (-not $p.HasExited) {
  $v = [int](nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits); if ($v -gt $peakV) { $peakV = $v }
  try { $p.Refresh(); if ($p.PeakWorkingSet64 -gt $peakRam) { $peakRam = $p.PeakWorkingSet64 } } catch {}
  Start-Sleep -Milliseconds 500
}
$p.WaitForExit(); $sw.Stop()
$summary = "stage=$Stage device=$Device samples=$Samples size=${Width}x$Height exit=$($p.ExitCode) seconds=$([math]::Round($sw.Elapsed.TotalSeconds,1)) peakRAM_MB=$([math]::Round($peakRam/1MB)) VRAM_before_MB=$vram0 VRAM_peak_MB=$peakV"
$summary | Tee-Object -FilePath ([IO.Path]::ChangeExtension($Out, ".stats.txt"))
if ($p.ExitCode -ne 0 -or -not (Test-Path $Out)) { Get-Content "$log.err" -Tail 20; Write-Error "render failed: $Out"; exit 1 }
