# P-3D-3: run render.py on the NVIDIA chip and record peak video memory next to its stats.
# pwsh -File C:\Users\Sam\.rostrum\waves\heavy.ps1 run "hem: H3 render" gpu pwsh -NoProfile -File <this> <stage> <out.png> [render.py options...]
$ErrorActionPreference = "Stop"
$here = $PSScriptRoot
$py = Join-Path $here "..\..\.venv-usd\Scripts\python.exe"
if (-not (Test-Path $py)) { Write-Error "no venv: uv venv --python C:\Python313\python.exe .venv-usd (see README)"; exit 1 }
$env:SHIM_MCCOMPAT = "0x800000001"   # NVIDIA Optimus: run this process's OpenGL on the RTX chip
$vram0 = [int](nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits)
$p = Start-Process -FilePath $py -ArgumentList (@("-I", "`"$here\render.py`"") + ($args | ForEach-Object { "`"$_`"" })) -PassThru -NoNewWindow
$peak = $vram0
while (-not $p.HasExited) {
  $v = [int](nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits); if ($v -gt $peak) { $peak = $v }
  Start-Sleep -Milliseconds 250
}
$p.WaitForExit()
"VRAM_before_MB=$vram0 VRAM_peak_MB=$peak (whole GPU, all processes)"
if ($p.ExitCode -ne 0) { Write-Error "render.py failed ($($p.ExitCode))"; exit $p.ExitCode }
$stats = [IO.Path]::ChangeExtension($args[1], ".stats.json")
$j = Get-Content $stats -Raw | ConvertFrom-Json
$j | Add-Member vram_before_mb $vram0 -Force; $j | Add-Member vram_peak_mb $peak -Force
$j | ConvertTo-Json -Depth 4 | Out-File -Encoding utf8 $stats
