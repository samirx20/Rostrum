# P-PAINT: render the still life with a chosen texture folder through Team Hem's Cycles build
# (read-only use), under the gpu lock, then view it through OCIO.
# pwsh -File render.ps1 <textures-dir> <out-dir> <name> [samples] [width] [height]
param([string]$Tex, [string]$Dir, [string]$Name, [int]$Samples = 128, [int]$Width = 1920, [int]$Height = 1080)
$ErrorActionPreference = "Stop"
$w = $PSScriptRoot
$hemRender = Join-Path $w "..\..\3d-painterly\render.ps1"   # our copy of Hem's script (same code as theirs)
$exe = "C:\Users\Sam\.t3\worktrees\Rostrum\team-hem\proofs\3d-product\.build\cycles\install\cycles.exe"
if (-not (Test-Path $exe)) { throw "Cycles build not found: $exe" }
New-Item -ItemType Directory -Force $Dir | Out-Null
$stage = Join-Path $Dir "_$Name.usda"
python -I "$w\stage.py" $Tex $stage; if ($LASTEXITCODE) { throw "stage failed" }
# Hem's render.ps1 finds cycles.exe relative to itself; ours has no build, so pass through a shim
$shim = Join-Path $Dir "_render_$Name.ps1"
(Get-Content $hemRender -Raw -Encoding utf8).Replace('Join-Path $PSScriptRoot "..\3d-product\.build\cycles\install\cycles.exe"', "`"$exe`"") |
  Set-Content $shim -Encoding utf8
pwsh -NoProfile -File C:\Users\Sam\.rostrum\waves\heavy.ps1 run "priyam: P2 render $Name" gpu `
  pwsh -NoProfile -File $shim $stage "$Dir\$Name.exr" $Samples $Width $Height
if ($LASTEXITCODE) { throw "render failed ($LASTEXITCODE)" }
uv run -q --with opencolorio --with openexr --with numpy --with pillow python -I "$w\..\..\3d-painterly\view.py" "$Dir\$Name.exr" "$Dir\$Name.png"
if ($LASTEXITCODE) { throw "view failed" }
Remove-Item $shim
"$Dir\$Name.png"
