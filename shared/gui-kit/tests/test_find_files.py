"""Find… for missing files: every file found in the chosen folder is linked again in ONE change (one undo step)."""
from rostrum_core import Who, toy

from rostrum_gui import find_files


def test_find_relinks_everything_found_as_one_undo_step(tmp_path):
    doc = toy.sample(tmp_path / "proj", "main")
    shots = tmp_path / "moved" / "deep"
    shots.mkdir(parents=True)
    (shots / "Logo.PNG").write_bytes(b"x")                        # found by name ignoring capitals
    (shots / "bg.jpg").write_bytes(b"x")
    refs = [("title", "name", str(tmp_path / "old" / "logo.png")), ("card", "name", str(tmp_path / "old" / "bg.jpg")),
            ("cam_1", "name", str(tmp_path / "old" / "gone.mov"))]
    made = find_files.relink(refs, tmp_path / "moved", lambda item: "layer.rename")
    assert len(made.found) == 2 and made.still_missing == [refs[2]]

    before = doc.seq
    doc.apply(made.calls, Who.person("sam"), label="Find 2 missing files")
    assert doc.seq == before + 1 and doc.item("title")["name"].endswith("Logo.PNG")
    doc.undo(Who.person("sam"))
    assert doc.item("title")["name"] != str(shots / "Logo.PNG") and doc.item("card")["name"] != str(shots / "bg.jpg")
