"""A scene not saved yet keeps its imported pictures in the app's temporary store; the first save into a project moves
them into the project (one change), so no "File outside the project" problem ever shows for them."""
import sys
from pathlib import Path

from PIL import Image
from rostrum_core import Document, Who
from rostrum2d import KIND, media
from rostrum2d.diagnose import problems
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from screen2d import files2d  # noqa: E402


def test_first_save_keeps_temporary_files_in_the_project(tmp_path):
    pic = media.import_dir(None, "t") / "red.png"
    pic.parent.mkdir(parents=True)
    Image.new("RGB", (20, 20), (255, 0, 0)).save(pic)
    doc = files2d.blank(None)
    doc.apply([{"op": "layer.add", "target": ["main"], "args": {"type": "image", "id": "pic", "name": "Pic"}},
               {"op": "image.set", "target": ["pic"], "args": {"src": str(pic), "w": 20, "h": 20}}], Who.person())
    folder = tmp_path / "proj"
    files2d.save_into(doc, folder)
    src = Document.open(folder, "main", KIND).item("pic")["src"]
    assert src.startswith("media/") and (folder / src).is_file()
    assert not [p for p in problems(doc.item("main"), folder) if p["kind"] == "outside-project"]
