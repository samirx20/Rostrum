"""The Sound document kind: its operations (registered by importing the ops modules), where items live,
a fresh document, and the whole-document check.

    root (doc: tempo, length, beatsPerBar, sampleRate)
      tracks[]   track: notes[] hits[] clips[] (clip: effects[]) lines[] (a voice track) effects[] automation[] sends[] ducks[]
      buses[]    bus: effects[] automation[]   (a track's `output` and a send's `bus` name a bus id)
      markers[]  marker: name, at
      master[]   the one master (id "master"): effects[] automation[]
"""
from __future__ import annotations

from rostrum_core import DocKind

from . import fields as FD
from . import ops_buses, ops_mix, ops_timed, ops_tracks, ops_voice  # noqa: F401  (they register the operations)
from .check import check
from .registry import LISTS, MASTER_ID, REGISTRY


def blank() -> dict:
    return {"id": "root", "type": "doc", **FD.DEFAULTS["doc"], "tracks": [], "buses": [], "markers": [],
            "master": [{"id": MASTER_ID, "type": "master", **FD.DEFAULTS["master"], "effects": [], "automation": []}]}


def facts(item: dict) -> dict:
    """What valid_when can ask about an item beyond its own fields: a track's lanes (its children)."""
    if item.get("type") != "track":
        return {}
    return {"vibratoLane": any(a.get("lane") == "vibrato" for a in item.get("automation", []))}


KIND = DocKind("sound", ".trk", REGISTRY, lists=LISTS, check=check, new=blank, facts=facts)
