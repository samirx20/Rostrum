# P-3D-2 look loop: write the stage, render it through the gpu lock, view it through OCIO.
# pwsh -File look.ps1 <out-dir> <name> [samples] [width] [height] [-Ramp] [-Grain 0.035]
param([string]$Dir, [string]$Name, [int]$Samples = 64, [int]$Width = 960, [int]$Height = 540,
      [switch]$Ramp, [switch]$Partial, [double]$Grain = 0)
$ErrorActionPreference = "Stop"
$w = $PSScriptRoot
$stageArgs = @("--out", "_$Name.usda"); if ($Ramp) { $stageArgs += "--ramp" }; if ($Partial) { $stageArgs += "--partial" }
python -I "$w\scene\make_scene.py" @stageArgs; if ($LASTEXITCODE) { throw "make_scene failed" }
pwsh -NoProfile -File C:\Users\Sam\.rostrum\waves\heavy.ps1 run "hem: H2 render $Name" gpu `
  pwsh -NoProfile -File "$w\render.ps1" "$w\scene\_$Name.usda" "$Dir\$Name.exr" $Samples $Width $Height
if ($LASTEXITCODE) { throw "render failed ($LASTEXITCODE)" }
$view = @("$Dir\$Name.exr", "$Dir\$Name-raw.png")
if ($Grain -gt 0) { $view += @("--grain", $Grain, "--grain-png", "$Dir\$Name-graded.png") }
uv run -q --with opencolorio --with openexr --with numpy --with pillow python -I "$w\view.py" @view
if ($LASTEXITCODE) { throw "view failed" }
