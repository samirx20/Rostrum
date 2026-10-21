"""A Sound render as a versioned hand-off (shared/HANDOFFS.md § 1, § 3, § 5): the mix and every track's stem
written into `renders/<item>/vNNN.partial/`, then the manifest, then renamed to `vNNN/`. So the Editor and the
project list (rostrum_core.project) see it, and a failed render stays `.partial`, never listed.

    r = handoff.render(folder, doc, engine, schedule, who="agent:claude-code")
    r["file"], r["stems"], r["version"], r["folder"]        # paths in the finished vNNN/ folder
"""
from __future__ import annotations

import time
from pathlib import Path

from rostrum_core import RostrumError, codes
from rostrum_core.project import begin_render, finish_render

ENGINE = "rostrum-sound-schedule/1"     # the contract the schedule was rendered through (names.CONTRACT)


def _file(name: str, meters: dict) -> dict:
    return {"file": name, "loudness_lufs": meters.get("lufs"), "true_peak_db": meters.get("truePeak", meters.get("peak")),
            "clipped_at": meters.get("clipped") or []}


def manifest(item: str, version: int, r: dict, doc, who: str, master: bool) -> dict:
    tracks = {t["id"]: t for t in r.get("tracks", [])}
    stems = {tid: Path(p).name for tid, p in r.get("stems", {}).items()}
    return {"item": item, "version": version, "kind": "sound", "made_by": who,
            "made_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "source": {"document": doc.item_id, "history_entry": doc.seq}, "engine": ENGINE,
            "sample_rate": doc.data.get("sampleRate", 48000), "bit_depth": "32-bit float",
            "seconds": r.get("seconds"), "mastered": master,
            # Master processing is on the mix only, and buses / sends sit between: the stems need not add up to it.
            "stems_add_up": not master and not doc.data.get("buses"),
            "mix": _file(Path(r["file"]).name, r), "stems": {tid: _file(n, tracks.get(tid, {})) for tid, n in stems.items()}}


def render(folder, doc, engine, schedule: dict, who: str, stems="all", master: bool = True) -> dict:
    """Render `schedule` into the next version of the document's item. Returns the engine's answer with
    `file` / `stems` pointing into the finished folder, plus `version` and `folder`. Any failure raises; the
    `.partial` folder stays, named in the error (HANDOFFS § 1)."""
    item = doc.item_id
    part = begin_render(folder, item)
    try:
        r = engine.request("render", schedule=schedule, out=str(part / f"{item}_mix.wav"), stems=stems,
                           stemsDir=str(part))
    except Exception as e:
        raise RostrumError(codes.JOB_FAILED, "render", str(part), f"failed and stays unfinished: {e}") from e
    if not Path(r["file"]).is_file():
        raise RostrumError(codes.JOB_FAILED, "render", str(part), "the engine answered but wrote no mix")
    version = int(part.name[1:-len(".partial")])
    done = finish_render(part, manifest(item, version, r, doc, who, master))
    moved = lambda p: str(done / Path(p).name)   # noqa: E731
    return {**r, "file": moved(r["file"]), "stems": {k: moved(p) for k, p in r.get("stems", {}).items()},
            "version": version, "folder": str(done)}
