"""Renaming the song reopens it in this window (the kit's ProjectFiles.rename): the Editor, its track, the selection and
the playhead come back (critic r12 should-fix 7), through Sound's `place` / `restore_place`. A place saved long ago
is left alone: a song opened later starts as before."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from screensound.bridge import SoundBridge  # noqa: E402
from screensound import song_slots  # noqa: E402
from test_screen import bridge  # noqa: E402,F401  (the screen's fixture: a small song, a stand-in engine)


def test_a_reopen_keeps_the_editor_track_selection_and_playhead(bridge):  # noqa: F811
    bridge.select("lead.n2000")
    bridge.workspace.setDock("editor")
    bridge.setTime(1.5)
    p = song_slots.place(bridge)
    again = SoundBridge(bridge.doc)                    # the window's new bridge on the reopened song
    try:
        song_slots.restore_place(again, p)
        assert again.workspace.dock == "editor"
        assert again.selectedIds == ["lead.n2000"] and again._track == "lead"
        assert abs(again._t - 1.5) < 1e-6
    finally:
        again.close()


def test_an_old_place_is_left_alone(bridge):  # noqa: F811
    bridge.select("lead.n2000")
    bridge.workspace.setDock("editor")
    p = {**song_slots.place(bridge), "saved": 0}
    again = SoundBridge(bridge.doc)
    try:
        song_slots.restore_place(again, p)
        assert again.workspace.dock == "" and again.selectedIds == []
    finally:
        again.close()
