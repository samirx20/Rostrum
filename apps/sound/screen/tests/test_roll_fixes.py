"""The Editor's fixes people rely on without seeing them break: a drum hit answers on both halves of its diamond, a
note's typed Swell / Vibrato / Bend reads back as typed, and Esc in a new marker's name box keeps the marker."""
from test_select import bridge  # noqa: F401  (the fixture: a small song, the engine stood in for)

from screensound import note_feel, pick


def test_a_hit_is_caught_either_side_of_its_time():
    roll = {"drums": ["kick", "snare"], "blocks": [{"id": "h", "type": "hit", "t": 1.0, "dur": 0.12, "drum": "snare"}]}
    assert pick.roll_at(roll, 0.95, 1, 0.08) == "h" == pick.roll_at(roll, 1.05, 1, 0.08)
    assert pick.roll_at(roll, 0.9, 1, 0.08) == "" and pick.roll_at(roll, 1.0, 0, 0.08) == ""


def test_typed_note_feel_reads_back_as_typed():
    for param, typed, secs in (("dynamics", "0.5 → 1.5", 1), ("vibrato", "40 cents · 6 Hz · after 0.2 s", 1),
                               ("bend", "0 → 200 cents", 0.5), ("bend", "-100 cents", 0.5)):
        assert note_feel.words(param, note_feel.parse(param, typed, secs), secs) == typed
    assert note_feel.parse("dynamics", "1", 1) is None and note_feel.parse("vibrato", "off", 1) is None


def test_esc_in_a_new_markers_name_keeps_the_marker(bridge):  # noqa: F811
    before = len(bridge.doc.data.get("markers", []))
    assert bridge.markerAt(1.0)
    mid = bridge.renaming
    bridge.finishRename(mid, "")                       # Esc: the renaming is cancelled, not the marker
    assert bridge.doc.has(mid) and len(bridge.doc.data["markers"]) == before + 1
    assert not bridge.markerAt(1.0)                    # M on the same spot: no second marker
    assert len(bridge.doc.data["markers"]) == before + 1 and bridge.selectedIds == [mid]
