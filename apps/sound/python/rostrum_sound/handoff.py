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


LIMITER_SLACK_DB = 0.05     # a reduction under this is inaudible and under the files' own rounding


def stems_rule(r: dict) -> dict:
    """The one stems rule (docs: guides/mixing-to-delivery.md): stems leave through the master's linear gain
    (fader, its automation, fades, the gain to the loudness target), never its glue, limiter or master effects.
    So they add up to the mix wherever none of those acted; this says whether that is everywhere, and by how
    much they differ where not."""
    m = r.get("master") or {}
    glue, limiter = m.get("glueMaxReductionDb", 0.0), m.get("limiterMaxReductionDb", 0.0)
    inserts = bool(m.get("insertsOnMix"))
    return {"rule": "stems carry the master's linear gain; its glue, limiter and master effects are on the mix only",
            "master_gain_db": m.get("gainDb", 0.0), "glue_max_reduction_db": glue, "limiter_max_reduction_db": limiter,
            "master_effects_on_mix_only": inserts,
            "stems_add_up": not inserts and glue <= LIMITER_SLACK_DB and limiter <= LIMITER_SLACK_DB}


def manifest(item: str, version: int, r: dict, doc, who: str, master: bool) -> dict:
    tracks = {t["id"]: t for t in r.get("tracks", [])}
    stems = {tid: Path(p).name for tid, p in r.get("stems", {}).items()}
    buses = {b["id"]: b for b in r.get("buses", [])}
    bus_stems = {bid: Path(p).name for bid, p in r.get("busStems", {}).items()}
    rule = stems_rule(r)
    return {"item": item, "version": version, "kind": "sound", "made_by": who,
            "made_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "source": {"document": doc.item_id, "history_entry": doc.seq}, "engine": ENGINE,
            "sample_rate": doc.data.get("sampleRate", 48000), "bit_depth": "32-bit float",
            "seconds": r.get("seconds"), "mastered": master,
            # Without buses the track stems add up to the mix; with buses, the stems of the tracks in `direct` plus
            # the bus stems do (a track feeding a bus is inside its bus) — under `stems_rule`.
            "stems_add_up": rule["stems_add_up"], "stems_rule": rule,
            "direct": r.get("direct", list(stems)),
            "mix": _file(Path(r["file"]).name, r), "stems": {tid: _file(n, tracks.get(tid, {})) for tid, n in stems.items()},
            "bus_stems": {bid: _file(n, buses.get(bid, {})) for bid, n in bus_stems.items()}}


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
            "busStems": {k: moved(p) for k, p in r.get("busStems", {}).items()},
            "version": version, "folder": str(done)}
