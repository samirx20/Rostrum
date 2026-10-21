"""More ways to hear (CONVENTIONS § 9): beats, pitch, clashes and harmony. Same rules as tools_look.py: they read the last
render (or a given WAV, or one stem by track id), answer in plain words plus data and a picture where it helps, and never
change the document. The analysis is in `rostrum_sound/ears/`."""
from __future__ import annotations

from pathlib import Path

import numpy as np
from rostrum_core import RostrumError, codes
from rostrum_core.mcp import Reply, Tools

from ..doc import tempo
from ..ears import beats as B
from ..ears import clash as C
from ..ears import engine_ears
from ..ears import harmony as H
from ..ears import pitch as P
from ..ears import voicing as V
from ..ears.draw import beats_picture, pitch_picture
from ..ears.draw_clash import clash_picture
from ..ears.written import instrument_spec, written_notes
from ..listen.core import load
from .tools_look import ITEM, WAV, _source

TRACK = {"track": {"type": "string", "description": "Read one track's stem (last render) instead of the mix."}}
DETAIL = {"detail": {"type": "string", "enum": ["short", "full"], "default": "short", "description": "short trims long lists; full lists everything."}}


def _pick(stems, track, where):
    if track not in stems:
        raise RostrumError.not_found(where, "stem", track, stems, "the last render's stems")
    return stems[track]


def _cap(rows, args, n=40):
    return rows if args.get("detail") == "full" or len(rows) <= n else rows[:n]


def register(tools: Tools):
    @tools.tool("look_beats", {"properties": {**ITEM, **WAV, **TRACK, **DETAIL,
        "stems": {"type": "boolean", "default": False, "description": "List the onsets of every stem, not just the mix."},
        "beats_per_bar": {"type": "integer", "description": "For the downbeat guess. Default: the document's."},
        "division": {"type": "integer", "default": 4, "description": "Grid to measure onsets against: 4 = sixteenth notes, 2 = eighths, 1 = beats."},
        "tolerance": {"type": "number", "default": 0.04, "description": "Seconds an onset may sit off the grid."}}})
    def look_beats(ctx, args):
        """Tempo (BPM, steady or drifting), the beat grid and a downbeat guess, each onset's distance in ms from the nearest beat or sixteenth, against the audio's own beats and the document's tempo map, with a waveform picture."""
        doc, wav, stems = _source(ctx, args, "look_beats")
        src = _pick(stems, args["track"], "look_beats") if args.get("track") else wav
        r = B.analyse_beats(src, args.get("beats_per_bar") or int(doc.data.get("beatsPerBar", 4)))
        div, tol = args.get("division", 4), args.get("tolerance", 0.04) * 1000
        sources = {args["track"]: src} if args.get("track") else {"mix": wav, **(stems if args.get("stems") else {})}
        audio_pos = B.audio_grid(r["beats_s"]) if len(r["beats_s"]) >= 2 else None
        use_doc = not args.get("wav")
        grids = {"against_audio_beats": audio_pos} if audio_pos else {}
        if use_doc:
            grids["against_document_tempo"] = (lambda t: tempo.beat_at(doc.data, t), lambda b: tempo.seconds_at(doc.data, b))
        out, pic_on = {}, []
        for name, f in sources.items():
            ons = B.stem_onsets(f)
            full = {k: B.grid_offsets(ons, *g, div, tol) for k, g in grids.items()}
            out[name] = {"onsets": len(ons), **{k: {**v, "items": _cap(v["items"], args)} for k, v in full.items()}}
            if not pic_on and full:           # the picture shows the first source against the document grid (else the audio's)
                pic_on = [(i["t"], i["off_ms"]) for i in list(full.values())[-1]["items"]]
        dur = r["duration_s"]
        doc_beats = tempo.beats(doc.data, dur) if use_doc else None
        png = ctx.app.state.look_dir(doc.item_id) / f"{Path(src).stem}-beats.png"
        beats_picture(png, src, r["beats_s"], r["downbeats_s"], pic_on, doc_beats, limit_ms=tol)
        r["onsets"], r["document_bpm"] = out, (tempo.start_bpm(doc.data) if use_doc else None)
        if use_doc:
            ratio = (r["bpm"] or 0) / r["document_bpm"]
            r["audio_vs_document"] = ("matches" if abs(ratio - 1) < 0.03 else "double" if abs(ratio - 2) < 0.06 else "half" if abs(ratio - 0.5) < 0.03 else "differs")
            r["document_tempo_changes"] = len(tempo.segments(doc.data)) > 1
        r["beats_s"], r["downbeats_s"] = _cap(r["beats_s"], args, 80), _cap(r["downbeats_s"], args, 40)
        main = next(iter(out.values()))
        s = (main.get("against_document_tempo") or main.get("against_audio_beats") or {}).get("summary")
        said = f"{r['bpm']} BPM, {r['steadiness']}" + (f" ({r['bpm_start']} → {r['bpm_end']})" if r["steadiness"] == "drifting" else "")
        said += f"; document {r['document_bpm']:g} BPM ({r['audio_vs_document']})" if use_doc else ""
        said += f"; {main['onsets']} onsets" + (f", median {s['median_abs_off_ms']} ms off the {s['grid']} grid, {s['within_limit_pct']:.0f}% within {tol:.0f} ms, leaning {s['lean']}" if s else "")
        return Reply(said + ".", r, [str(png)], [str(png)])

    @tools.tool("look_pitch", {"properties": {**ITEM, **WAV, **TRACK, **DETAIL,
        "fmin": {"type": "number", "description": "Lowest pitch to look for, Hz (default: from the written notes, else 65)."},
        "fmax": {"type": "number", "description": "Highest pitch, Hz (default: from the written notes, else 1500)."},
        "cents_tolerance": {"type": "number", "default": 25, "description": "Cents a note may be off before it is out of tune."},
        "timing_tolerance": {"type": "number", "default": 0.06, "description": "Seconds a note may start early or late."}}})
    def look_pitch(ctx, args):
        """The pitch of one melodic line as notes with times and cents off (vibrato, drift, tuning); with a track, each written note checked for wrong note, wrong octave, late, out of tune or missing. A picture of the curve over a note grid with the written notes as bars. One note at a time: use a single-voice stem."""
        doc, wav, stems = _source(ctx, args, "look_pitch")
        tid = args.get("track")
        src = _pick(stems, tid, "look_pitch") if tid else wav
        written = written_notes(doc.data, [tid]) if tid else []
        lo = min((m for w in written for m in w["midis"]), default=None)
        hi = max((m for w in written for m in w["midis"]), default=None)
        fmin = args.get("fmin") or (float(np.clip(440 * 2 ** ((lo - 12 - 69) / 12), 40, 2000)) if lo is not None else 65.0)
        fmax = args.get("fmax") or (float(np.clip(440 * 2 ** ((hi + 12 - 69) / 12), 80, 4000)) if hi is not None else 1500.0)
        t, midi, _ = P.pitch_track(src, fmin, fmax)
        heard = P.segment_notes(t, midi)
        r = {"notes": _cap(heard, args, 60), "notes_total": len(heard), "tuning_offset_cents": P.tuning_offset(heard),
             "vibrato_notes": [n["note"] + f"@{n['start']}" for n in heard if n["vibrato"]],
             "drifting_notes": [f"{n['note']}@{n['start']} ({n['drift_cents']:+g} cents)" for n in heard if n["drift_cents"] and abs(n["drift_cents"]) >= 25],
             "range_hz": [round(fmin), round(fmax)]}
        rows = None
        if written:
            cmp = P.compare(written, heard, args.get("cents_tolerance", 25), args.get("timing_tolerance", 0.06))
            rows = cmp["rows"]
            r["comparison"] = {**cmp, "rows": rows if args.get("detail") == "full" else [x for x in rows if x["status"] != "ok"][:60]}
        png = ctx.app.state.look_dir(doc.item_id) / f"{Path(src).stem}-pitch.png"
        pitch_picture(png, t, midi, written, rows)
        said = f"{len(heard)} notes heard" + (f"; the line sits {r['tuning_offset_cents']:+g} cents from equal temperament" if heard else "")
        said += f"; vibrato on {len(r['vibrato_notes'])}, drift on {len(r['drifting_notes'])}"
        if rows is not None:
            said += f". Against {len(written)} written notes: " + ", ".join(f"{n} {k.replace('_', ' ')}" for k, n in r["comparison"]["counts"].items())
        elif not tid:
            said += ". No track given, so nothing to compare with (pitch of the mix follows its loudest line)"
        return Reply(said + ".", r, [str(png)], [str(png)])

    @tools.tool("look_clash", {"properties": {**ITEM, **DETAIL,
        "tracks": {"type": "array", "items": {"type": "string"}, "description": "Only these tracks' stems (default all, up to 12)."},
        "within_db": {"type": "number", "default": 6, "description": "Two stems clash where both are loud and within this many dB of each other."},
        "floor_db": {"type": "number", "default": -45, "description": "Band level (dB, a full-scale sine is about -3) under which a stem doesn't count as there."},
        "min_length": {"type": "number", "default": 0.3, "description": "Shortest clash to report, seconds."}}})
    def look_clash(ctx, args):
        """Where two stems fight in the same frequency band at the same time: spans (start, end, band in Hz, the two tracks, how many dB each stands over the other), worst first, and a time × band picture coloured by pair. Needs the last render's stems."""
        doc, _, stems = _source(ctx, args, "look_clash")
        if not stems:
            raise RostrumError(codes.NOT_FOUND, "look_clash", "stems", "were not rendered", hint="render_mix with stems: true.")
        want = args.get("tracks") or list(stems)
        levels, hop = C.stem_levels({t: _pick(stems, t, "look_clash") for t in want})
        spans, maps = C.find_clashes(levels, args.get("within_db", 6), args.get("floor_db", -45), args.get("min_length", 0.3), hop)
        png = ctx.app.state.look_dir(doc.item_id) / "clash.png"
        clash_picture(png, maps, spans, hop)
        r = {"clashes": _cap(spans, args, 30), "total": len(spans), "tracks": list(levels), "within_db": args.get("within_db", 6),
             "floor_db": args.get("floor_db", -45), "note": "a clash is both stems loud in one band; `<a>_over_<b>_db` > 0 means a stands over b by that much (b is the one buried)"}
        return Reply(f"{len(spans)} clashes among {len(levels)} tracks" + (f"; worst: {C.line(spans[0])}" if spans else "") + ".", r, [str(png)], [str(png)])

    @tools.tool("inspect_harmony", {"properties": {**ITEM, **WAV, **TRACK,
        "source": {"type": "string", "enum": ["auto", "notes", "audio"], "default": "auto", "description": "auto: the document's notes when it has any, else the audio's chroma."},
        "per": {"type": "string", "enum": ["bar", "beat"], "default": "bar"},
        "key": {"type": "string", "description": "Check notes against this key (\"D minor\") instead of the document's key map or the estimate."},
        "checks": {"type": "boolean", "default": True, "description": "Voicing checks on the written notes: range, low close intervals, crossings, wide spacing, out of key."}}})
    def inspect_harmony(ctx, args):
        """Key (from the document's key map, its notes or the audio), the chord per bar or beat, and voicing checks as plain facts: notes outside the instrument's range, close intervals too low, voices crossing, upper voices over an octave apart, notes out of key."""
        doc = ctx.document(args.get("item"))
        tid = args.get("track")
        notes = written_notes(doc.data, [tid] if tid else None)
        use_notes = args.get("source", "auto") == "notes" or (args.get("source", "auto") == "auto" and notes and not args.get("wav"))
        per = args.get("per", "bar")
        r: dict = {"source": "notes" if use_notes else "audio", "document_keys": [k.get("key") for k in doc.data.get("keys", [])]}
        warnings, chroma = [], None
        if use_notes:
            if not notes:
                raise RostrumError(codes.NOT_FOUND, "inspect_harmony", "notes", "none written in the document" + (f" for track {tid}" if tid else ""))
            end = max(n["end"] for n in notes)
            est = H.key_from_notes(notes)
            rows = H.chart_from_notes(notes, H.windows(doc.data, end, per), H.speller(doc.data, args.get("key"), est))
        else:
            _, wav, stems = _source(ctx, args, "inspect_harmony")
            src = _pick(stems, tid, "inspect_harmony") if tid else wav
            chroma, ct = H.chroma_of(src)
            y, sr = load(src)
            est = engine_ears.key_of_audio(src)        # the engine's key: the one source for audio (ears/engine_ears.py)
            rows = H.chart_from_audio(chroma, ct, H.windows(doc.data, len(y) / sr, per), H.speller(doc.data, args.get("key"), est))
        r["key_estimate"], r["chords"] = est, rows
        used = args.get("key") or (est["key"] if est["key"] else None)
        r["key_used_for_checks"] = used
        if use_notes and args.get("checks", True):
            ranges, unchecked = {}, {}
            for t in sorted({n["track"] for n in notes}):
                spec = instrument_spec(doc.data, t)
                if not spec or not set(spec) & {"builtIn", "sfz"}:
                    unchecked[t] = "its instrument has no fixed range to ask the engine for"
                    continue
                try:
                    rg = ctx.app.state.engine.request("range", instrument={k: spec[k] for k in spec if k in ("builtIn", "sfz")})
                    ranges[t] = (rg["lowKey"], rg["highKey"])
                except Exception as e:                       # the engine said no: say so, don't pretend the range was fine
                    unchecked[t] = f"engine range request failed: {e}"
                    warnings.append(f"range of {t} not checked: {e}")
            found = [*V.range_problems(notes, ranges), *V.stack_problems(notes), *V.crossings(notes), *V.out_of_key(notes, doc.data, used)]
            found.sort(key=lambda e: e["at_s"])
            r["checks"] = {"problems": _cap(found, {**args, "detail": args.get("detail")}, 40), "total": len(found),
                           "counts": {k: sum(e["kind"] == k for e in found) for k in sorted({e["kind"] for e in found})},
                           "range_unchecked": unchecked, "low_interval_limits": "common orchestration chart, simplified (ears/theory.py LOW_LIMIT)"}
        bars = [x for x in rows if x["beat"] == 1] if per == "beat" else rows
        r["progression"] = " | ".join(x["chord"] for x in bars[:32]) + (" …" if len(bars) > 32 else "")
        said = f"Key {H.key_line(est, r['source'])}" + (f", checked against {used}" if use_notes else "")
        said += f". Chords: {r['progression']}."
        if "checks" in r:
            c = r["checks"]["counts"]
            said += " Checks: " + (", ".join(f"{n} {k.replace('_', ' ')}" for k, n in c.items()) if c else "no problems found") + "."
        return Reply(said, r, warnings=warnings)

