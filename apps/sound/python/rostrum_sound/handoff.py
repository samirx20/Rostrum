"""A Sound render as a versioned hand-off (shared/HANDOFFS.md § 1, § 3, § 5): the mix and every track's stem
written into `renders/<item>/vNNN.partial/`, then the manifest, then renamed to `vNNN/`. So the Editor and the
project list (rostrum_core.project) see it. A failed or stopped render removes its `.partial` folder: nothing half-written is left behind.

    r = handoff.render(folder, doc, engine, schedule, who="agent:claude-code")
    r["file"], r["stems"], r["version"], r["folder"]        # paths in the finished vNNN/ folder
"""
from __future__ import annotations

import json
import math
import shutil
import time
from pathlib import Path

from rostrum_core import RostrumError, codes
from rostrum_core.project import begin_render, finish_render

from . import deliver, packs, stem_groups
from .doc import markers, times

ENGINE = "rostrum-sound-schedule/1"     # the contract the schedule was rendered through (names.CONTRACT)


def _file(name: str, meters: dict) -> dict:
    return {"file": name, "loudness_lufs": meters.get("lufs"), "true_peak_db": meters.get("truePeak", meters.get("peak")),
            "clipped_at": meters.get("clipped") or []}


def _stem(name: str, written: dict | None, track: dict, clipped: int) -> dict:
    """A stem as the manifest says it: the file's own loudness and peaks (the engine measured it as it wrote it; an
    older engine's track meters otherwise) and the samples cut flat at full scale in it (a fixed-point file)."""
    m = written or track
    return {"file": name, "loudness_lufs": m.get("lufs"), "true_peak_db": m.get("truePeak", m.get("peak")),
            "sample_peak_db": (written or {}).get("peak"), "clipped_samples": clipped}


LIMITER_SLACK_DB = 0.05     # a reduction under this is inaudible and under the files' own rounding
ADD_UP = 1e-4               # the stems' sum within this of the mix (sample value, -80 dB) adds up to it


def stems_rule(r: dict) -> dict:
    """The one stems rule (docs: guides/mixing-to-delivery.md): stems carry the master's whole gain (fader, its
    automation, fades, glue, the gain to the loudness target and the limiter, worked out once on the mix and the same
    on every stem), so they add up to the mix. What the master does that a stem cannot carry (its effects, its reverb,
    time warps, a loop's wrap, the safety clip) is named in `on_mix_only`; the engine measures how far the sum is from
    the mix when the stems hold everything that reaches the master."""
    m = r.get("master") or {}
    only, diff = m.get("onMixOnly"), m.get("stemsMaxDifference")
    base = {"master_gain_db": m.get("gainDb", 0.0), "glue_max_reduction_db": m.get("glueMaxReductionDb", 0.0),
            "limiter_max_reduction_db": m.get("limiterMaxReductionDb", 0.0)}
    if only is None:            # an engine from before the shared gain: its stems carry the linear gain only
        return {"rule": "stems carry the master's linear gain only (an older engine): glue, limiter and master effects are on the mix only",
                **base, "on_mix_only": ["glue", "limiter", "master effects"], "stems_add_up": False}
    rule = ("stems carry the master's whole gain: fader, fades, glue, loudness gain and limiter, one gain curve worked "
            "out on the mix and the same on every stem")
    return {"rule": rule + (f"; on the mix only: {', '.join(only)}" if only else ""), **base, "on_mix_only": only,
            **({"max_difference": diff, "max_difference_db": round(20 * math.log10(max(diff, 1e-12)), 1)} if diff is not None else {}),
            "stems_add_up": not only and (diff is None or diff <= ADD_UP)}


def manifest(item: str, version: int, r: dict, doc, who: str, master: bool, names: dict | None = None) -> dict:
    names = names or {}
    tracks = {t["id"]: t for t in r.get("tracks", [])}
    stems = {tid: Path(p).name for tid, p in r.get("stems", {}).items()}
    buses = {b["id"]: b for b in r.get("buses", [])}
    bus_stems = {bid: Path(p).name for bid, p in r.get("busStems", {}).items()}
    rule = stems_rule(r)
    clipped = r.get("clippedFiles") or {}
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
            "clipped_samples": r.get("clippedSamples", 0), "clipped_files": r.get("clippedFiles") or {}, "mastered": master,
            **({"credits": lines} if (lines := packs.credit_lines(r)) else {}),    # CC-BY instruments: credit them where the sound goes
            "mix": _file(Path(r["file"]).name, r),
            **_stems_part(r, stems, bus_stems, rule, tracks, buses, clipped, names)}


def _stems_part(r, stems, bus_stems, rule, tracks, buses, clipped, names) -> dict:
    """What the manifest says about stems: nothing at all when none were made (an empty `stems` beside `stems_add_up: true`
    claimed something about files that do not exist). Without buses the track stems add up to the mix; with buses, the
    stems of the tracks in `direct` plus the bus stems do (a track feeding a bus is inside its bus), under `stems_rule`."""
    if not stems and not bus_stems:
        return {}
    return {"stems_add_up": rule["stems_add_up"], "stems_rule": rule,
            "direct": r.get("direct", list(stems)),
            # the id → file mapping: the file is named after the track as the screen shows it, the key is its id
            "stems": {tid: {**_stem(n, (r.get("stemMeters") or {}).get(tid), tracks.get(tid, {}), clipped.get(n, 0)),
                            "name": names.get(tid, tid)} for tid, n in stems.items()},
            "bus_stems": {bid: {**_stem(n, (r.get("busStemMeters") or {}).get(bid), buses.get(bid, {}), clipped.get(n, 0)),
                                "name": names.get(bid, bid)} for bid, n in bus_stems.items()}}


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


SILENT_DB = -90.0


def silent_stems(r: dict, names: dict) -> list[str]:
    """The names of stems that came out silent (an empty track): they are written all the same, so the export says so."""
    meters = {t["id"]: t for t in [*r.get("tracks", []), *r.get("buses", [])]}
    out = []
    for i in [*r.get("stems", {}), *r.get("busStems", {})]:
        m = meters.get(i) or {}
        peak = m.get("peak", m.get("truePeak"))
        if i in meters and (peak is None or peak <= SILENT_DB):
            out.append(names.get(i, i))
    return out


def warnings(r: dict) -> list[str]:
    """What a person must know about the files, in plain words (empty: nothing): a file cut flat at full scale, and
    stems that do not add up to the mix (what the master did that they cannot carry). Shown by the Export sheet's
    result line and the render reply, never left to the manifest alone."""
    out = list(r.get("warnings") or [])        # the engine's own (the song's ending: engine/src/contract/ending.rs)
    clipped = r.get("clippedFiles") or {}
    if clipped:
        out.append("Clipped: " + ", ".join(f"{Path(n).stem} ({k:,} samples cut flat)" for n, k in clipped.items())
                   + ". Export as WAV 32-bit float to keep every peak, or turn those tracks down")
    rule = stems_rule(r)
    if (r.get("stems") or r.get("busStems")) and not rule["stems_add_up"]:
        why = ", ".join(rule["on_mix_only"]) if rule["on_mix_only"] else "the master"
        out.append(f"The stems do not add up to the mix exactly: {why} {'is' if len(rule['on_mix_only']) == 1 else 'are'} on the mix only")
    return out


def names_of(doc, ids) -> dict:
    """{id: the name the screen shows} for tracks and buses (the id when it has no name)."""
    return {i: (doc.item(i).get("name") or i) if doc.has(i) else i for i in ids}


def render(folder, doc, engine, schedule: dict, who: str, stems="all", master: bool = True, options: dict | None = None,
           markers_file: bool = False, say=None) -> dict:
    """Render `schedule` into the next version of the document's item. Returns the engine's answer with
    `file` / `stems` pointing into the finished folder, plus `version` and `folder`. Any failure or stop raises, and the
    `.partial` folder is removed (HANDOFFS § 1). `options` is `deliver.Options.read`'s request: the
    file format, sample rate and trimming the silent end (default: 24-bit WAV at the song's rate, trimmed). The
    files are named after the tracks; the manifest keeps the id → file mapping. `stems`: "all" (a file per track and per group),
    a list of track ids, [] (none) or "groups" (a stem per group and per ungrouped track: stem_groups.py).
    `markers_file`: also write `markers.json` beside the files (the Editor preset). `say(words)`: what it is doing now
    (the Export sheet shows it)."""
    opts = deliver.Options.read(options, doc.data.get("sampleRate", 48000))      # a wrong choice answers before any folder is made
    part = begin_render(folder, doc.item_id)
    try:
        return _render(part, folder, doc, engine, {**schedule, "sampleRate": opts.sample_rate}, who, stems, master, opts, markers_file,
                       say or (lambda _w: None))
    except BaseException:                  # failed, or stopped (a cancel): no `vNNN.partial` is left to look like a render
        shutil.rmtree(part, ignore_errors=True)
        raise


def _render(part, folder, doc, engine, schedule, who, stems, master, opts, markers_file, say) -> dict:
    item = doc.item_id
    say("Rendering the mix and its stems" if stems else "Rendering the mix")
    try:
        rng = {} if opts.start is None else {"from": opts.start, "to": opts.end}       # the engine renders the range itself
        r = engine.request("render", schedule=schedule, out=str(part / deliver.mix_name(item)),
                           stems="all" if stems == "groups" else stems, stemsDir=str(part), **rng)
    except Exception as e:
        raise RostrumError(codes.JOB_FAILED, "render", str(part), f"failed: {e}") from e
    if not Path(r["file"]).is_file():
        raise RostrumError(codes.JOB_FAILED, "render", str(part), "the engine answered but wrote no mix")
    try:
        if stems == "groups":
            r = stem_groups.keep(r, doc.data)
        if markers_file:
            write_markers(part, doc, folder, None if opts.start is None else (opts.start, opts.end))
            r = {**r, "markersFile": MARKERS_FILE}
        names = names_of(doc, [*r.get("stems", {}), *r.get("busStems", {})])
        n = len(r.get("stems") or {}) + len(r.get("busStems") or {})
        say(f"Writing {deliver.mix_name(item, opts.spec['ext'])}" + (f" and {n} stem{'s' * (n != 1)}" if n else "")
            + f" as {opts.spec['label']}")
        r = deliver.deliver(part, r, names, opts, item)
    except RostrumError:
        raise
    except Exception as e:
        raise RostrumError(codes.JOB_FAILED, "render", str(part), f"could not write the {opts.spec['label']} files: {e}") from e
    version = int(part.name[1:-len(".partial")])
    done = finish_render(part, manifest(item, version, r, doc, who, master, names))
    moved = lambda p: str(done / Path(p).name)   # noqa: E731
    return {**r, "silentStems": silent_stems(r, names), "warnings": warnings(r), "file": moved(r["file"]), "stems": {k: moved(p) for k, p in r.get("stems", {}).items()},
            "busStems": {k: moved(p) for k, p in r.get("busStems", {}).items()},
            "version": version, "folder": str(done)}
