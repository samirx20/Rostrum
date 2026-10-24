"""Doubled controls merged on the screen: a clip's Pitch + Keep speed (the document keeps both fields), plug-ins
listed once each, and an Output row only when there is a group to send to."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from screensound import output_pick, pitch_merge, plugin_rows


def test_keep_speed_moves_the_amount_to_the_other_field_and_pitch_writes_the_one_in_use():
    clip = {"type": "clip", "pitch": 0, "shift": 3}
    assert pitch_merge.keeps_speed(clip) and pitch_merge.amount(clip) == 3
    assert pitch_merge.edit_args(clip, "Keep speed", False) == {"pitch": 3.0, "shift": 0}       # tape-style: same amount
    assert pitch_merge.edit_args(clip, "Pitch", 5) == {"shift": 5}
    tape = {"type": "clip", "pitch": -2}
    assert not pitch_merge.keeps_speed(tape) and pitch_merge.edit_args(tape, "Pitch", 4) == {"pitch": 4}
    assert pitch_merge.edit_args({"type": "clip"}, "pitch", 1) is None                         # the plain row (several clips) is not ours


def test_a_plugin_in_two_formats_is_listed_once_in_the_best_format():
    catalog = [{"kind": "effect", "name": "Surge XT Effects", "vendor": "Surge", "format": f, "path": f"p.{f}", "id": "x"} for f in ("vst3", "clap")]
    rows = plugin_rows.one_each(catalog, "effect", lambda p: p["path"])
    assert rows == [{"id": "p.clap", "label": "Surge XT Effects"}]


def test_output_has_nothing_to_pick_until_there_is_a_group():
    track = {"id": "t1", "type": "track", "output": "master"}
    assert output_pick.nowhere_else({"buses": []}, track)
    assert not output_pick.nowhere_else({"buses": [{"id": "bus_1"}]}, track)
