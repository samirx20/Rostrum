"""A Sound render as a versioned hand-off (shared/HANDOFFS.md § 1, § 3, § 5): the mix and every track's stem
written into `renders/<item>/vNNN.partial/`, then the manifest, then renamed to `vNNN/`. So the Editor and the
project list (rostrum_core.project) see it, and a failed render stays `.partial`, never listed.

    r = handoff.render(folder, doc, engine, schedule, who="agent:claude-code")
    r["file"], r["stems"], r["version"], r["folder"]        # paths in the finished vNNN/ folder
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from rostrum_core import RostrumError, codes
from rostrum_core.project import begin_render, finish_render

from . import deliver, stem_groups
from .doc import markers, times

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


def manifest(item: str, version: int, r: dict, doc, who: str, master: bool, names: dict | None = None) -> dict:
    names = names or {}
    tracks = {t["id"]: t for t in r.get("tracks", [])}
    stems = {tid: Path(p).name for tid, p in r.get("stems", {}).items()}
    buses = {b["id"]: b for b in r.get("buses", [])}
    bus_stems = {bid: Path(p).name for bid, p in r.get("busStems", {}).items()}
    rule = stems_rule(r)
    return {"item": item, "version": version, "kind": "sound", "made_by": who,
            "made_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "source": {"document": doc.item_id, "history_entry": doc.seq}, "engine": ENGINE,
            "markers": markers.used(doc.data),          # the project / own marker times this render was made for
            "sample_rate": r.get("sampleRate", doc.data.get("sampleRate", 48000)),
            "format": r.get("format", {"id": "wav32f", "label": "WAV 32-bit float", "container": "WAV", "subtype": "FLOAT", "ext": "wav"}),
            "bit_depth": {"PCM_16": "16-bit", "PCM_24": "24-bit", "FLOAT": "32-bit float"}.get((r.get("format") or {}).get("subtype", "FLOAT"), "lossy (MP3)"),
            "seconds": r.get("seconds"), "song_seconds": r.get("songSeconds", r.get("seconds")), "trimmed_silence": r.get("trimmed", False),
            **({"range": r["range"]} if r.get("range") else {}),
            **({"stems_by": r["stemsBy"]} if r.get("stemsBy") else {}), **({"markers_file": MARKERS_FILE} if r.get("markersFile") else {}),
            "clipped_samples": r.get("clippedSamples", 0), "mastered": master,
            # Without buses the track stems add up to the mix; with buses, the stems of the tracks in `direct` plus
            # the bus stems do (a track feeding a bus is inside its bus) — under `stems_rule`.
            "stems_add_up": rule["stems_add_up"], "stems_rule": rule,
            "direct": r.get("direct", list(stems)),
            "mix": _file(Path(r["file"]).name, r),
            # the id → file mapping: the file is named after the track as the screen shows it, the key is its id
            "stems": {tid: {**_file(n, tracks.get(tid, {})), "name": names.get(tid, tid)} for tid, n in stems.items()},
            "bus_stems": {bid: {**_file(n, buses.get(bid, {})), "name": names.get(bid, bid)} for bid, n in bus_stems.items()}}


MARKERS_FILE = "markers.json"


def write_markers(part: Path, doc, folder, span=None) -> None:
    """The named markers and the sections as data beside the files (`markers.json`): `{"unit": "seconds", "markers":
    [{name, seconds}], "sections": [{name, start, end}]}`, times from the start of the delivered files (a range's start is
    taken off; what lies outside it is left out). For the Editor preset (presets.py)."""
    a, b = span if span else (0.0, float("inf"))
    with markers.project(folder):
        found = [{"name": n, "seconds": round(t - a, 4)} for n, t in markers.all(doc.data) if a <= t <= b]
        secs = [{"name": s.get("name") or s["id"], "start": round(times.seconds(s["at"], doc.data, s["id"]) - a, 4),
                 "end": round(times.seconds(s["end"], doc.data, s["id"]) - a, 4)} for s in doc.data.get("sections", [])]
    secs = [s for s in secs if s["end"] > 0 and s["start"] < b - a]
    (part / MARKERS_FILE).write_text(json.dumps({"unit": "seconds", "markers": found, "sections": secs}, indent=2), encoding="utf-8")


def names_of(doc, ids) -> dict:
    """{id: the name the screen shows} for tracks and buses (the id when it has no name)."""
    return {i: (doc.item(i).get("name") or i) if doc.has(i) else i for i in ids}


def render(folder, doc, engine, schedule: dict, who: str, stems="all", master: bool = True, options: dict | None = None,
           markers_file: bool = False) -> dict:
    """Render `schedule` into the next version of the document's item. Returns the engine's answer with
    `file` / `stems` pointing into the finished folder, plus `version` and `folder`. Any failure raises; the
    `.partial` folder stays, named in the error (HANDOFFS § 1). `options` is `deliver.Options.read`'s request: the
    file format, sample rate and trimming the silent end (default: 24-bit WAV at the song's rate, trimmed). The
    files are named after the tracks; the manifest keeps the id → file mapping. `stems`: "all" (a file per track and per group),
    a list of track ids, [] (none) or "groups" (a stem per group and per ungrouped track: stem_groups.py).
    `markers_file`: also write `markers.json` beside the files (the Editor preset)."""
    item = doc.item_id
    opts = deliver.Options.read(options, doc.data.get("sampleRate", 48000))
    schedule = {**schedule, "sampleRate": opts.sample_rate}
    part = begin_render(folder, item)
    try:
        rng = {} if opts.start is None else {"from": opts.start, "to": opts.end}       # the engine renders the range itself
        r = engine.request("render", schedule=schedule, out=str(part / f"{item}_mix.wav"),
                           stems="all" if stems == "groups" else stems, stemsDir=str(part), **rng)
    except Exception as e:
        raise RostrumError(codes.JOB_FAILED, "render", str(part), f"failed and stays unfinished: {e}") from e
    if not Path(r["file"]).is_file():
        raise RostrumError(codes.JOB_FAILED, "render", str(part), "the engine answered but wrote no mix")
    try:
        if stems == "groups":
            r = stem_groups.keep(r, doc.data)
        if markers_file:
            write_markers(part, doc, folder, None if opts.start is None else (opts.start, opts.end))
            r = {**r, "markersFile": MARKERS_FILE}
        names = names_of(doc, [*r.get("stems", {}), *r.get("busStems", {})])
        r = deliver.deliver(part, r, names, opts, item)
    except RostrumError:
        raise
    except Exception as e:
        raise RostrumError(codes.JOB_FAILED, "render", str(part), f"could not write the {opts.spec['label']} files and stays unfinished: {e}") from e
    version = int(part.name[1:-len(".partial")])
    done = finish_render(part, manifest(item, version, r, doc, who, master, names))
    moved = lambda p: str(done / Path(p).name)   # noqa: E731
    return {**r, "file": moved(r["file"]), "stems": {k: moved(p) for k, p in r.get("stems", {}).items()},
            "busStems": {k: moved(p) for k, p in r.get("busStems", {}).items()},
            "version": version, "folder": str(done)}
