"""The Export sheet's choices are kept with the song (critic r12 should-fix 2): stems picked and the sheet closed without
exporting are still picked at the next open, after a reopen of the song too, and cleaning the renders folder doesn't
lose them (they used to come only from the newest export's manifest)."""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtGui import QGuiApplication  # noqa: E402
from rostrum_core import Document  # noqa: E402
from rostrum_sound import KIND, run_source  # noqa: E402
from screensound import playback  # noqa: E402
from screensound.bridge import SoundBridge  # noqa: E402
from screensound.files_sound import ITEM  # noqa: E402
from screensound.mixer import MixPage  # noqa: E402
from test_screen import FakeEngine  # noqa: E402

SRC = '''
a = track("bass", builtIn="feltPiano")
for i in range(8):
    a.note(36 + i, at=beat(i), dur=beats(1))
'''


def _sheet(folder):
    b = SoundBridge(Document.open(folder, ITEM, KIND))
    MixPage(b, b)
    b.exporter.watch(True)                              # the sheet opens
    return b


def test_stems_picked_without_exporting_come_back(tmp_path, monkeypatch):
    QGuiApplication.instance() or QGuiApplication([])
    monkeypatch.setattr(playback, "open_engine", FakeEngine)
    doc = Document.new(KIND, folder=tmp_path / "S", item=ITEM)
    doc.run_script("song.py", run_source(SRC, "song.py"))
    doc.save()
    b = _sheet(tmp_path / "S")
    assert b.exporter.stemsMode == "off"
    b.exporter.setStemsMode("all")
    b.exporter.setMarkers(True)
    b.exporter.watch(False)                             # closed without exporting
    b.close()

    shutil.rmtree(tmp_path / "S" / "renders", ignore_errors=True)   # renders cleaned: nothing to read back from
    again = _sheet(tmp_path / "S")
    assert again.exporter.stemsMode == "all"
    assert again.exporter.markers is True
    again.close()
