"""The Sound document kind: its operations (registered by importing the ops modules), where items live,
a fresh document, and the whole-document check.

    root (doc: tempo, length, beatsPerBar, sampleRate)
      tracks[]   track: notes[] hits[] clips[] sounds[] (designed sounds) (clip: effects[]) lines[] (a voice track) effects[] automation[] sends[] ducks[]
      buses[]    bus: effects[] automation[]   (a track's `output` and a send's `bus` name a bus id)
      markers[]  marker: name, at
      master[]   the one master (id "master"): effects[] automation[]
      tempos[]   tempo: at, bpm (the tempo map with doc tempo: tempo.py)   keys[]  key: at, key   sections[]  section: name, at, end
"""
from __future__ import annotations

from rostrum_core import DocKind

from .. import names
from . import fields as FD
from . import ops_bus_tracks, ops_buses, ops_cleanup, ops_mix, ops_music, ops_range, ops_fit, ops_section_copy, ops_select_clips, ops_select_move, ops_select_notes, ops_select_place, ops_select_tracks, ops_swap, ops_timed, ops_tracks, ops_voice  # noqa: F401  (they register the operations)
from . import fields_design as FDS
from .check import check
from .registry import LISTS, MASTER_ID, REGISTRY


def blank() -> dict:
    return {"id": "root", "type": "doc", **FD.DEFAULTS["doc"], "tracks": [], "buses": [], "markers": [], "tempos": [], "keys": [], "sections": [],
            "master": [{"id": MASTER_ID, "type": "master", **FD.DEFAULTS["master"], "effects": [], "automation": []}]}


def _playing(track: dict) -> dict:
    """How a track's notes may be played: the facts a note's art / touch fields ask (doc/playing.py NOTE)."""
    model = track.get("model") if track.get("instrument") == "model" else None
    return {"struck": model is not None and model not in names.BOWED, "plucked": model in names.PLUCKED,
            "articulated": track.get("instrument") == "sfz" and bool(track.get("articulations"))}


def facts(item: dict, doc=None) -> dict:
    """What valid_when can ask about an item beyond its own fields: a track's lanes (its children), and how its
    notes are played; a note asks its track (doc is a View, so a note sees its parent)."""
    if item.get("type") == "note":
        track = doc.parent(item) if doc is not None else None
        return _playing(track) if track else {}
    if item.get("type") != "track":
        return {}
    return {"vibratoLane": any(a.get("lane") == "vibrato" for a in item.get("automation", [])), **_playing(item)}


KIND = DocKind("sound", ".trk", REGISTRY, lists=LISTS, check=check, warn=FDS.retired, new=blank, facts=facts)
