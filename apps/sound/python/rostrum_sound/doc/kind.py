"""The Sound document kind: its operations (the ops modules in rostrum_sound/modules.py), where items live,
a fresh document, and the whole-document check.

    root (doc: tempo, length, beatsPerBar, sampleRate)
      tracks[]   track: notes[] hits[] clips[] (clip: effects[]) lines[] (a voice track) effects[] automation[] sends[] ducks[]
      buses[]    bus: effects[] automation[]   (a track's `output` and a send's `bus` name a bus id)
      markers[]  marker: name, at
      master[]   the one master (id "master"): effects[] automation[]
      tempos[]   tempo: at, bpm (the tempo map with doc tempo: tempo.py)   keys[]  key: at, key   sections[]  section: name, at, end
"""
from __future__ import annotations

from rostrum_core import DocKind

from .. import names
from . import dropped, markers, media, migrations, past_end
from . import fields as FD
from ..modules import OPS
from .check import check
from .registry import LISTS, MASTER_ID, REGISTRY

OPS.load()                    # they register the operations (rostrum_sound/modules.py)


def blank() -> dict:
    return {"id": "root", "type": "doc", **FD.DEFAULTS["doc"], "tracks": [], "buses": [], "markers": [], "tempos": [], "meters": [], "keys": [], "sections": [],
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
    lanes = {a.get("lane") for a in item.get("automation", [])}
    return {"vibratoLane": "vibrato" in lanes, "bendLane": "bend" in lanes, **_playing(item)}


def elsewhere(id_: str) -> str | None:
    """A target that is not in the song but is one of the project's markers (changed with edit_markers)."""
    mark = next((r for r in markers.project_rows() if r["id"] == id_), None)
    return mark and (f'"{mark["name"]}" is a marker the whole project shares, not part of this song: change it with '
                     f'edit_markers (marker.move / marker.rename), so 2D and the Editor see it too.')


KIND = DocKind("sound", ".trk", REGISTRY, lists=LISTS, version=migrations.FORMAT, migrations=migrations.STEPS, upgraded=migrations.upgraded, check=check, elsewhere=elsewhere, warn=lambda data: dropped.warn(data) + past_end.warn(data), new=blank, facts=facts, upgrade=media.upgrade, tidy=media.tidy)
