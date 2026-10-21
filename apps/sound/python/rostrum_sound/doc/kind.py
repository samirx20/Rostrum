"""The Sound document kind: its operations (registered by importing the ops modules), where items live,
a fresh document, and the whole-document check.

    root (doc: tempo, length, beatsPerBar, sampleRate)
      tracks[]   track: notes[] hits[] clips[] (clip: effects[]) effects[] automation[]
      markers[]  marker: name, at
      master[]   the one master (id "master"): effects[] automation[]
"""
from __future__ import annotations

from rostrum_core import DocKind

from . import fields as FD
from . import ops_mix, ops_timed, ops_tracks  # noqa: F401  (they register the operations)
from .check import check
from .registry import LISTS, MASTER_ID, REGISTRY


def blank() -> dict:
    return {"id": "root", "type": "doc", **FD.DEFAULTS["doc"], "tracks": [], "markers": [],
            "master": [{"id": MASTER_ID, "type": "master", **FD.DEFAULTS["master"], "effects": [], "automation": []}]}


KIND = DocKind("sound", ".trk", REGISTRY, lists=LISTS, check=check, new=blank)
