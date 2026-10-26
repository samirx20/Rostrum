"""The Export sheet starts from the choices the song's last export was made with (critic r10 must-fix 3: a mix-only export
then a stem export of the same song state reopened as "Only the mix", and the next file went out without stems)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from screensound.export_versions import last_choices  # noqa: E402

SOURCE = {"document": "song", "history_entry": 155}


def made(folder, v, **m):
    d = folder / "renders" / "song" / f"v{v:03d}"
    d.mkdir(parents=True)
    (d / "manifest.json").write_text(json.dumps({"version": v, "source": SOURCE, "format": {"id": "wav24"}, **m}),
                                     encoding="utf-8")


def test_the_sheet_reads_its_own_choices_back(tmp_path):
    made(tmp_path, 1, export_sheet={"format": "wav24", "trim": True, "stems": "off", "markers": False})
    made(tmp_path, 2, stems={"strings": {}}, export_sheet={"format": "wav24", "trim": True, "stems": "all", "markers": False})
    made(tmp_path, 3, format={"id": "mp3"})               # "+ Another version" of the same run: no stems, no sheet
    assert last_choices(tmp_path, "song")["stems"] == "all"


def test_older_exports_of_one_song_state_keep_the_stems(tmp_path):
    made(tmp_path, 1)                                      # mix only
    made(tmp_path, 2, stems={"strings": {}})               # then the same state with a stem per track (no sheet record)
    assert last_choices(tmp_path, "song")["stems"] == "all"
