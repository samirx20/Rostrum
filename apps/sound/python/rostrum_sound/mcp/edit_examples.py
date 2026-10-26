"""Whole `edit_document` calls, one per kind of operation agents use: the arguments exactly as the tool takes them.

Each line is the complete JSON `arguments` of one edit_document call; they are what edit_document's description shows and
what guides/start-here.md prints (run against a real song when written; keep the two in step). `ops` is the list key, a
track is a target by its id ("drums", not "track.drums"), a note or hit operation takes ids or a range target
(range_target.py), a time is {"beat": n} and a length is {"beats": n}.
"""
LINES = (
    ("Make a chord on every note of bar 1-8 of a track (a range target: from included, to not; bars count from 1)",
     '{"ops": [{"op": "note.chord", "target": [{"track": "guitar", "from": {"bar": 1}, "to": {"bar": 9}}], "args": {"shape": "minor"}}]}'),
    ("Transpose up a fifth, notes of bars 1-8",
     '{"ops": [{"op": "note.transpose", "target": [{"track": "guitar", "from": {"bar": 1}, "to": {"bar": 9}}], "args": {"semitones": 7}}]}'),
    ("Strum the chords of a whole track (no from / to = all of it)",
     '{"ops": [{"op": "note.strum", "target": [{"track": "guitar"}], "args": {"gap": 30, "soften": 0.1}}]}'),
    ("Repeat bars 1-4 once, 16 beats later; notes you name by id work too",
     '{"ops": [{"op": "note.duplicate", "target": [{"track": "guitar", "from": {"bar": 1}, "to": {"bar": 5}}], "args": {"by": {"beats": 16}, "times": 1}}]}'),
    ("Fill a hi-hat row (the TRACK is the target; from and to are beats here, not bars)",
     '{"ops": [{"op": "hit.fill", "target": ["drums"], "args": {"drum": "hat", "every": 0.5, "from": {"beat": 0}, "to": {"beat": 32}, "vel": 0.8}}]}'),
    ("Repeat the drum hits of bars 1-4 three times",
     '{"ops": [{"op": "hit.duplicate", "target": [{"track": "drums", "from": {"bar": 1}, "to": {"bar": 5}}], "args": {"by": {"beats": 16}, "times": 3}}]}'),
    ("Add a section (at / end, not start) and a marker",
     '{"ops": [{"op": "section.add", "args": {"name": "verse", "at": {"beat": 0}, "end": {"beat": 32}}}, {"op": "marker.add", "args": {"name": "drop", "at": {"beat": 32}}}]}'),
    ("Set a track's volume in dB",
     '{"ops": [{"op": "track.set", "target": ["drums"], "args": {"volume": {"db": -4}}}]}'),
)


def as_text() -> str:
    return "\n".join(f"{what}: {call}" for what, call in LINES)
