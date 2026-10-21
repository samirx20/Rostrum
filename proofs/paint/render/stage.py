"""Write P-3D-2's still-life stage with textures from a folder we choose (P-PAINT before / after).

    python -I stage.py <textures-dir> <out.usda> [--ramp]

Reuses proofs/3d-painterly/scene (make_scene.py, materials.py) unchanged; only the texture
folder moves, so Team Hem's files are never written to. Missing textures fail loudly
(materials.image raises).
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCENE = os.path.normpath(os.path.join(HERE, "..", "..", "3d-painterly", "scene"))
sys.path.insert(0, SCENE)
import materials  # noqa: E402
import make_scene  # noqa: E402

if len(sys.argv) < 3:
    raise SystemExit(__doc__)
tex, out = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
if not os.path.isdir(tex):
    raise SystemExit(f"texture folder not found: {tex}")
materials.TEX = tex
sys.argv = ["make_scene.py", "--out", out] + (["--ramp"] if "--ramp" in sys.argv[3:] else [])
make_scene.main()
