"""A picture or video belongs to the project: import keeps it inside (stored by its place in the folder), so copying
the project and deleting the original still draws it; an older project's absolute paths are made relative on open (one
undoable change); a missing file fails loudly naming the layer and the file; a file kept outside stays, and diagnose says so."""
import shutil
from pathlib import Path
import subprocess

import pytest
from PIL import Image
from rostrum_core import Document, RostrumError, Who

from rostrum2d import KIND, settings
from rostrum2d.diagnose import problems
from rostrum2d.io import importing
from rostrum2d.scene import describe

pytestmark = pytest.mark.skipif(settings.engine_missing_reason() is not None, reason=settings.engine_missing_reason() or "")
BLANK = [{"op": "comp.add", "args": {"id": "main", "name": "Main", "width": 160, "height": 90, "fps": 10, "duration": 1.0}}]


def _project(tmp_path):
    pic = tmp_path / "red.png"
    Image.new("RGB", (40, 40), (255, 0, 0)).save(pic)
    clip = tmp_path / "blue.mp4"
    subprocess.run([settings.ffmpeg(), "-v", "error", "-f", "lavfi", "-i", "color=c=blue:s=64x64:d=1:r=10", "-pix_fmt", "yuv420p",
                    str(clip)], check=True, creationflags=settings.NO_WINDOW)
    folder = tmp_path / "proj"
    doc = Document.new(KIND, folder, "main", start=BLANK)
    for path in (pic, clip):
        importing.run(doc, Who.person(), "main", path)
    doc.save()
    return folder, pic, clip


def test_pictures_and_videos_survive_moving_the_project(tmp_path):
    from rostrum2d.engine import Engine
    folder, pic, clip = _project(tmp_path)
    srcs = [i["src"] for i in Document.open(folder, "main", KIND).items() if i.get("type") in ("image", "video")]
    assert sorted(srcs) == sorted(s for s in srcs if s.startswith("media/")) and len(srcs) == 2    # stored by place, not full path
    moved = tmp_path / "elsewhere" / "proj"
    shutil.copytree(folder, moved)
    shutil.rmtree(folder)
    pic.unlink(), clip.unlink()
    opened = Document.open(moved, "main", KIND)
    with Engine() as eng:
        eng.load(describe(opened.data, "main", folder=moved))
        eng.still(0.5, tmp_path / "frame.png")
    assert (tmp_path / "frame.png").stat().st_size > 0
    (moved / srcs[0]).unlink()                                                    # truly missing: loud, names layer and file
    with pytest.raises(RostrumError) as e:
        describe(opened.data, "main", folder=moved)
    assert Path(srcs[0]).name in str(e.value) and ("red" in str(e.value) or "blue" in str(e.value))


def test_older_absolute_paths_become_relative_on_open_and_outside_files_are_kept(tmp_path):
    folder, pic, _ = _project(tmp_path)
    doc = Document.open(folder, "main", KIND)
    layer = next(i for i in doc.items() if i.get("type") == "image")
    inside = str(folder / layer["src"])
    doc.apply([{"op": "image.set", "target": [layer["id"]], "args": {"src": inside}},
               {"op": "layer.add", "target": ["main"], "args": {"type": "image", "id": "away", "name": "Away"}},
               {"op": "image.set", "target": ["away"], "args": {"src": str(pic), "w": 10, "h": 10}}], Who.person())
    doc.save()
    reopened = Document.open(folder, "main", KIND)
    assert reopened.item(layer["id"])["src"] == layer["src"] and reopened.item("away")["src"] == str(pic)
    comp = reopened.item("main")
    assert [p["kind"] for p in problems(comp, folder) if p["kind"] == "outside-project"] == ["outside-project"]
