"""Preview equals export for light (brief 10b): the quick view (Storm) and Final (Cycles) light a grey floor alike for
every light kind, by UsdLux's units. Guards the units Cycles is given (a small bulb once rendered hundreds of times
brighter in Final, the same at any radius) and Storm's sphere-normalize and spot fixes (core/src/storm_lights.h).
Needs the built engine and a GPU; skipped without them."""
import numpy as np
import pytest
from rostrum_core import Document

from rostrum3d import KIND, run_source
from rostrum3d.compile import describe
from rostrum3d.runtime import find_exe

W, H = 192, 108
BASE = '''
grey = material("grey", baseColor="#808080", roughness=0.9)
mesh("floor", shape="plane", width=10, depth=10, material=grey)
cam = camera("cam", focalLength=30, y=3.0, z=3.0).aim((0, 0, 0))
shot("hero", camera=cam, fps=24, start=0, end=1)
'''
LIGHTS = {  # kind: (the light, how far Quick may be from Final)
    "bulb": ('light("k", kind="sphere", radius=0.05, intensity=400, y=1.0)', 0.1),
    "bulb normalized": ('light("k", kind="sphere", radius=0.05, intensity=20, y=1.0, normalize=True)', 0.1),
    "spot": ('light("k", kind="spot", radius=0.05, cone=60, softness=0.3, intensity=1500, y=2.0).aim((0, 0, 0))', 0.1),
    "softbox": ('light("k", kind="rect", width=1, height=1, intensity=6, y=1.5).aim((0, 0, 0))', 0.15),  # Storm: a point
    "sun": ('light("k", kind="distant", intensity=2, angle=1, rx=-73.3, normalize=True)', 0.1),
}


@pytest.fixture(scope="module")
def engine():
    if not find_exe().exists():
        pytest.skip("3D engine not built")
    from rostrum3d.engine import Engine
    with Engine() as eng:
        yield eng


def linear(px):
    a = np.asarray(px, np.float64)[..., :3] / 255
    return np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)


def patch(a):
    return a[H // 2 - 10:H // 2 + 10, W // 2 - 15:W // 2 + 15].mean()


@pytest.mark.parametrize("kind", list(LIGHTS))
def test_quick_lights_the_floor_like_final(engine, kind, tmp_path):
    from PIL import Image
    src, tolerance = LIGHTS[kind]
    doc = Document.new(KIND)
    doc.run_script("s.py", run_source(BASE + src, "s.py"))
    engine.load(describe(doc.data, "hero"))
    look = {"view": "Un-tone-mapped"}  # no tone curve: the floor's own light, about 0.15-0.35 for each light here
    v, w, h, stride, _ = engine.view(camera="cam", frame=0, width=W, height=H, renderer="storm", ao=0, dof=False,
                                     studio=0, **look)
    try:
        quick = np.frombuffer(v, np.uint8).reshape(h, stride)[:, :w * 4].reshape(h, w, 4).copy()
    finally:
        v.release()
    png = tmp_path / "final.png"
    engine.render(camera="cam", renderer="cycles", frame=0, width=W, height=H, samples=64, png=str(png), **look)
    q, f = patch(linear(quick)), patch(linear(Image.open(png).convert("RGB")))
    assert f > 0.05, f"{kind}: Final left the floor black ({f})"
    assert abs(q / f - 1) <= tolerance, f"{kind}: quick {q:.4f} against final {f:.4f} (x{q / f:.2f})"


# KNOWN OPEN: Quick 1.47x Final (Storm's second copy of the scene dome; dropping it from Storm blacked out Quick, so
# that fix is out until it is found how the sky reaches Storm without it). The grey wash is gone (matte fallback).
@pytest.mark.xfail(reason="KNOWN OPEN: Storm lights a material-less item with the dome twice", strict=False)
def test_quick_colours_an_item_without_material_like_final(engine, tmp_path):
    # An item with only a colour (an import's displayColor, no material) is drawn by Storm's fallback shading. It added
    # Storm's own copy of the scene dome on top of the sky handed over, plus a shiny default material's grey: ~2.3x too
    # bright and washed out in Quick (core/src/storm_lights.cpp, hydra.cpp matte). A card lying flat sees the whole sky
    # in both renderers, so it must match; walls and undersides differ (Storm's sky has no shadow).
    from PIL import Image
    (tmp_path / "card.usda").write_text('#usda 1.0\n(\ndefaultPrim = "Root"\nmetersPerUnit = 1\nupAxis = "Y"\n)\n'
                                        'def Xform "Root"\n{\ndef Plane "Card"\n{\nuniform token axis = "Y"\n'
                                        'double width = 4\ndouble length = 4\n'
                                        'color3f[] primvars:displayColor = [(0.8, 0.25, 0.2)]\n}\n}\n')
    src = ('light("sky", kind="dome", intensity=0.5)\n'
           f'import_usd("card", file={str(tmp_path / "card.usda")!r}, y=0.01)\n'
           'cam = camera("cam", focalLength=30, y=3.0, z=3.0).aim((0, 0, 0))\n'
           'shot("hero", camera=cam, fps=24, start=0, end=1)\n')
    doc = Document.new(KIND)
    doc.run_script("s.py", run_source(src, "s.py"))
    engine.load(describe(doc.data, "hero"))
    look = {"view": "Un-tone-mapped"}
    v, w, h, stride, _ = engine.view(camera="cam", frame=0, width=W, height=H, renderer="storm", ao=0, dof=False,
                                     studio=0, **look)
    try:
        quick = np.frombuffer(v, np.uint8).reshape(h, stride)[:, :w * 4].reshape(h, w, 4).copy()
    finally:
        v.release()
    png = tmp_path / "final.png"
    engine.render(camera="cam", renderer="cycles", frame=0, width=W, height=H, samples=64, png=str(png), **look)
    rgb = [linear(a)[H // 2 - 10:H // 2 + 10, W // 2 - 15:W // 2 + 15].reshape(-1, 3).mean(axis=0)
           for a in (quick, Image.open(png).convert("RGB"))]
    (qr, qg, _), (fr, fg, _) = rgb
    assert fr > 0.05, f"Final left the card dark ({rgb[1]})"
    assert abs(qg / qr - fg / fr) <= 0.05, f"greyed: green/red quick {qg / qr:.3f}, final {fg / fr:.3f}"
    assert abs(qr / fr - 1) <= 0.15, f"red quick {qr:.4f} against final {fr:.4f} (x{qr / fr:.2f})"
