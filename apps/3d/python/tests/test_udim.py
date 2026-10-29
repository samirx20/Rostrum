"""UDIM sets (PR6): picking one tile picks the set only when another tile is beside it, and paint.export writes each
painted channel as tile 1001 plus a manifest naming the set."""
import json

from rostrum_core import Document, Who

from rostrum3d import KIND, run_source, udim, unfold

SAM = Who.person()


def _touch(folder, *names):
    for n in names:
        (folder / n).write_bytes(b"x")


def test_one_tile_becomes_the_set_only_with_another_tile(tmp_path):
    _touch(tmp_path, "skin.1001.png", "skin.1002.png", "skin.1011.png", "lone_1001.png", "wood.1001.tif")
    _touch(tmp_path, "wood_1002.tif")                         # another pattern ("_"): not the same set as "wood.1001"
    s = str(tmp_path / "skin.1002.png")
    assert udim.as_set(s) == str(tmp_path / "skin.<UDIM>.png")
    assert udim.tile_numbers(udim.as_set(s)) == [1001, 1002, 1011]
    assert udim.tiles(udim.as_set(s))[0] == str(tmp_path / "skin.1001.png")
    for keep in ("lone_1001.png", "wood.1001.tif", "plain.png", "shot.0001.png", "shot.1100.png"):
        assert udim.as_set(str(tmp_path / keep)) == str(tmp_path / keep)
    assert udim.as_set("") == ""
    assert udim.describe(udim.as_set(s)).startswith("UDIM set, 3 tiles (1001-1011)")


def test_export_writes_tile_1001_and_manifest(tmp_path):
    unfold.use_unfold(lambda doc, id_, size: {"uvs": [0.25, 0.75] * 6, "charts": 1, "used": 0.5})
    d = Document.new(KIND, folder=tmp_path, item="scene")
    d.run_script("lid.py", run_source('mesh("lid", shape="cylinder", radius=0.03, height=0.01)\n'
                                      'cam = camera("cam", z=0.4)\nshot("hero", camera=cam, fps=24, start=0, end=1)\n',
                                      "lid.py"))
    d.apply({"op": "mesh.unfold", "target": ["lid"]}, SAM)
    d.apply({"op": "paint.add", "target": ["lid"], "args": {"id": "scuffs", "channel": "roughness"}}, SAM)
    d.apply({"op": "stroke.add", "target": ["scuffs"],
             "args": {"points": [[100, 100, 1], [400, 300, 0.5]], "color": "#b0b0b0", "size": 40}}, SAM)
    d.apply({"op": "paint.export", "target": ["lid"], "args": {"folder": str(tmp_path / "out")}}, SAM)
    out = tmp_path / "out"
    manifest = json.loads((out / "lid_paint.json").read_text(encoding="utf-8"))
    assert manifest["channels"]["roughness"]["file"] == "lid_roughness.1001.png"
    assert manifest["channels"]["roughness"]["set"] == "lid_roughness.<UDIM>.png"
    assert (out / "lid_roughness.1001.png").stat().st_size > 100
    assert list(manifest["channels"]) == ["roughness"]
