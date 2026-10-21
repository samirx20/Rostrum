# P-3D-1 look loop: regenerate the stage, render through the gpu lock, tone-map to PNG.
# pwsh -File look.ps1 <out-name> [samples] [width] [height] [exposure]
param([string]$Name, [int]$Samples = 64, [int]$Width = 960, [int]$Height = 540, [double]$Exposure = 0)
$w = $PSScriptRoot; $s = "C:\Users\Sam\.rostrum\waves\scratch\hem-H1"
python -I "$w\scene\make_scene.py" | Out-Null; if ($LASTEXITCODE) { throw "make_scene failed" }
pwsh -File C:\Users\Sam\.rostrum\waves\heavy.ps1 run "hem: look render" gpu pwsh -File "$w\render.ps1" "$w\scene\product.usda" "$s\$Name.exr" $Samples OPTIX $Width $Height | Select-Object -Last 1
if ($LASTEXITCODE) { throw "render failed" }
uv run -q --with openexr --with numpy --with pillow python -I "$w\tonemap.py" "$s\$Name.exr" "$s\$Name.png" --exposure $Exposure
