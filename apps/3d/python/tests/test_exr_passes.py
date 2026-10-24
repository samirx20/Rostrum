"""Passes as EXR layers (brief 15): the channels in the EXR file are exactly the ones its manifest records, and each mask
names its item, so the Editor and agents can read a render by its manifest. Needs the built engine and a GPU (a tiny
Cycles frame); skipped without them."""
from pathlib import Path

import pytest
from rostrum_core import Document

from rostrum3d import KIND, run_source
from rostrum3d.compile import describe, shot_info
from rostrum3d.mcp.render import DocView, still
from rostrum3d.render_fields import PASSES
from rostrum3d.runtime import find_exe

SCENE = '''
grey = material("grey", baseColor="#808080", roughness=0.9)
mesh("floor", shape="plane", width=10, depth=10, material=grey)
mesh("box", name="The box", shape="box", y=0.5, material=grey)
light("key", kind="rect", width=1, height=1, intensity=6, x=1, y=2.5, z=1).aim((0, 0, 0))
cam = camera("cam", focalLength=30, y=2.0, z=4.0).aim((0, 0.5, 0))
shot("hero", camera=cam, fps=24, start=0, end=1)
'''


def exr_channels(path: Path) -> list[str]:
    """The channel names in an OpenEXR file's header (its `channels` attribute), read without any EXR library."""
    b = path.read_bytes()
    assert b[:4] == b"\x76\x2f\x31\x01", f"{path} is not an OpenEXR file"

    def text(at: int) -> tuple[str, int]:
        end = b.index(b"\0", at)
        return b[at:end].decode(), end + 1

    at = 8
    while b[at] != 0:
        name, at = text(at)
        _, at = text(at)                                        # the attribute's type
        size = int.from_bytes(b[at:at + 4], "little")
        at += 4
        if name == "channels":
            out, j = [], at
            while b[j] != 0:
                ch, j = text(j)
                out.append(ch)
                j += 16                                         # pixel type, linear, reserved, x/y sampling
            return out
        at += size
    raise AssertionError(f"{path} has no channel list")


def test_exr_layers_are_the_ones_the_manifest_records(tmp_path):
    if not find_exe().exists():
        pytest.skip("3D engine not built")
    import json

    from rostrum3d.engine import Engine
    doc = Document.new(KIND)
    doc.run_script("s.py", run_source(SCENE, "s.py"))
    info = shot_info(doc.data, "hero")
    with Engine() as engine:
        done, files, _ = still("test", DocView("scene", 1, doc.data), info, describe(doc.data, "hero"), engine, 0, "cycles",
                               (64, 36), ["exr"], 0, {"samples": 2, "denoise": False}, tmp_path, list(PASSES))
    manifest = json.loads((done / "manifest.json").read_text(encoding="utf-8"))["exr"]
    assert sorted(exr_channels(files[0])) == sorted(manifest["channels"])
    assert set(manifest["layers"]) == {"beauty", "light", "reflections", "rest", "shadow", "masks", "depth", "normal"}
    assert manifest["masks"]["masks.box"] == {"item": "box", "name": "The box"}
    assert "masks.floor" in manifest["masks"] and "masks.key" not in manifest["masks"] and "masks.cam" not in manifest["masks"]
