"""The song's clock: everything a note's or hit's block reads besides its own item (block_memo.py keeps the blocks
while it stays equal). That is the song's settings (tempo and its map, meter, keys, sections …) and only the markers
some time is written on ("#drop+0.5", in a track, a setting or another marker), the song's own and the project's
shared ones. A marker nothing is placed on is read by no block, so moving it keeps every block: a marker dragged on a
3-minute song made all ~3,300 blocks again at the drop (46-121 ms) though none had moved.

The references are found per track and kept while the track is the very same object (the document is never changed
in place), so a step that changed no track (a marker drag) looks at no item, and an edit looks at only its track.
"""
from __future__ import annotations

from rostrum_sound.doc import markers as mk

OWN = ("tracks", "buses", "master")     # what no other track's block reads (stepped.py: the mix rows are always made)
_SEEN: dict = {}                        # id(track) -> (the track, the marker names written in it)


def _names(node) -> frozenset:
    return frozenset(mk.ref(r) for r in mk.refs_in(node))


def _track_names(track: dict) -> frozenset:
    held = _SEEN.get(id(track))
    if held is None or held[0] is not track:
        held = _SEEN[id(track)] = (track, _names(track))
    return held[1]


def used(root: dict) -> frozenset:
    """The names of the markers some time in the song is written on."""
    tracks = root.get("tracks", [])
    if len(_SEEN) > 4 * len(tracks) + 64:                # forget tracks long gone (ids are reused only once freed)
        live = {id(t) for t in tracks}
        for k in [k for k in _SEEN if k not in live]:
            del _SEEN[k]
    out = set(_names({k: v for k, v in root.items() if k not in OWN}))
    for t in tracks:
        out |= _track_names(t)
    return frozenset(out)


def clock(root: dict) -> tuple:
    """Blocks made under an equal clock are still right."""
    names = used(root)
    marks = tuple(m for m in root.get("markers", []) if m.get("name", m["id"]) in names)
    return ({k: v for k, v in root.items() if k not in OWN and k != "markers"}, marks,
            tuple(r for r in mk.project_rows() if r.get("name") in names))
