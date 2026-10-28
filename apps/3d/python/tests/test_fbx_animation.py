"""FBX animation, skins (convert_fbx_anim.cpp) where a slip would go unseen: a hand-written file (files/skinned_bend.fbx)
whose cube slides 1 -> 2 m while turning 0 -> 180 deg over 1 s, and whose 2 m bar bends at 1 m by its second bone
(60 deg at 0.5 s). The converted layer must carry those motions at the right size (an earlier try showed a 3 m bar)."""
import re
from pathlib import Path

import pytest

from rostrum3d.runtime import find_exe

FBX = Path(__file__).parent / "files" / "skinned_bend.fbx"
T = {"visible": True, "x": 0, "y": 0, "z": 0, "rx": 0, "ry": 0, "rz": 0, "sx": 1, "sy": 1, "sz": 1}


def _samples(text: str, prim: str, attr: str) -> dict[int, str]:
    """{time code: value text} of `attr`'s time samples under the first `def … "prim"` in a flattened .usda."""
    body = text[text.index(f'"{prim}"'):]
    block = body[body.index(f"{attr}.timeSamples"):]
    block = block[:block.index("}")]
    return {int(t): v for t, v in re.findall(r"(\d+): (.+?),?\n", block)}


def _numbers(s: str) -> list[float]:
    return [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?(?:e-?\d+)?", s)]


def test_fbx_cube_slides_and_turns_and_the_bar_bends_at_its_size(tmp_path):
    if not find_exe().exists():
        pytest.skip("3D engine not built")
    from rostrum3d.engine import Engine
    scene = {"format": "rostrum-3d-scene", "version": 1, "shot": {"id": "s", "fps": 30, "start": 0, "end": 30, "shutter": 0},
             "world": {"background": [0, 0, 0], "environment": None}, "materials": [],
             "items": [{"id": "imp", "type": "import", "props": dict(T, file=str(FBX), prim="", material="", parts=[])}]}
    with Engine() as e:
        info = e.inspect_usd(FBX)
        e.load(scene)
        e.save(tmp_path / "flat.usda", flatten=True)
    assert info["animated"] and (info["startFrame"], info["endFrame"]) == (0, 30)
    bar = next(p for p in info["prims"] if p["path"].endswith("/Bar/Bar"))
    assert bar["bounds"][1][1] - bar["bounds"][0][1] == pytest.approx(2.0, abs=1e-4)   # 2 m, not 3

    text = (tmp_path / "flat.usda").read_text()
    spin = _samples(text, "Spinner", "xformOp:transform")
    m0, m15, m30 = (_numbers(spin[f]) for f in (0, 15, 30))
    assert m0[12:15] == pytest.approx([1, 0.5, 0]) and m30[12:15] == pytest.approx([2, 0.5, 0])   # slides 1 -> 2 m
    assert m15[0] == pytest.approx(0, abs=1e-6) and m30[0] == pytest.approx(-1)                   # turned 90, then 180 deg

    top = _numbers(_samples(text, "Bar", "points")[15])[24:27]       # point 8: the top ring's corner (-0.1, 2, -0.1)
    assert top == pytest.approx([-0.1 * 0.5 - 0.866025, 1 - 0.1 * 0.866025 + 0.5, -0.1], abs=1e-4)  # 60 deg about (0, 1, 0)
