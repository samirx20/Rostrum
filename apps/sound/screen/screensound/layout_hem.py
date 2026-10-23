"""Layout-check projects for what Team Hem asked for (P30): two songs in one project (which one is the main mix), and
a song carrying 2D's "Cues from 2D" track, its clips tied to project markers. Each returns start args for main.py."""
from __future__ import annotations

import tempfile
import wave
from pathlib import Path

from rostrum_core import Document, Who, markers
from rostrum_sound import KIND
from rostrum_sound.doc import markers as song_markers

LONG_MARKER = "Logo_lands_on_the_title_card_after_the_whole_second_verse_and_bridge"


def _project(root: str) -> Path:
    folder = Path(tempfile.mkdtemp(dir=root)) / "project"
    folder.mkdir()
    return folder


def two_songs(root: str, open_item: str, long_name: bool = False) -> list[str]:
    """alpha (first by name, so the main mix until another is marked) and beta; opens `open_item`."""
    folder = _project(root)
    for item in ("alpha", "beta"):
        Document.new(KIND, folder=str(folder), item=item).save()
    return ["--doc", str(folder), open_item]


def cues_song(root: str, marker: str = "Logo lands") -> list[str]:
    """A song with a pad and 2D's cue track: two clips tied to project markers (one with an offset)."""
    folder = _project(root)
    sound = folder.parent / "cue.wav"
    with wave.open(str(sound), "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(24000), w.writeframes(b"\x40\x10" * 24000 * 2)
    who = Who.person()
    markers.edit(folder, [{"op": "marker.add", "args": {"name": n, "at": t, "id": f"mk_cue_logo_{i}", "owner": "2d"}}
                          for i, (n, t) in enumerate([(marker, 2.0), ("Card slides in", 5.0)])], who, label="Cue markers")
    doc = Document.new(KIND, folder=str(folder), item="song")
    with song_markers.project(folder):
        doc.apply([{"op": "track.add", "args": {"id": "pad", "instrument": "synth", "synth": "saw"}},
                   {"op": "note.add", "target": ["pad"], "args": {"pitch": "D3", "at": 0.0, "dur": 4.0}},
                   {"op": "track.add", "args": {"id": "cues_2d", "name": "Cues from 2D"}},
                   {"op": "clip.add", "target": ["cues_2d"], "args": {"id": "cue_logo", "media": str(sound), "at": f"#{marker}"}},
                   {"op": "clip.add", "target": ["cues_2d"], "args": {"id": "cue_card", "media": str(sound), "at": "#Card slides in+0.25"}}],
                  who, label="Sound cues from 2D")
    doc.save()
    return ["--doc", str(folder), "song"]
