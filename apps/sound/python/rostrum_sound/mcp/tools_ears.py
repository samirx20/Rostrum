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
from ..ears import chords_heard as CH
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


def _out_of_key_line(found: list) -> str:
    """Which notes on which tracks are out of key, so the clashing part is named in the summary: " Out of key: lead Bb4 ×8 …"."""
    seen: dict = {}
    for e in found:
        if e["kind"] == "out_of_key":
            for t in e["tracks"]:
                for n in e["notes"]:
                    seen.setdefault(t, {}).setdefault(n, []).extend([e["at_s"]] * e.get("count", 1))
    if not seen:
        return ""
    return " Out of key: " + "; ".join(f"{t} " + ", ".join(f"{n} ×{len(at)} (from {min(at):.1f} s)" for n, at in notes.items())
                                       for t, notes in seen.items()) + "."


def register(tools: Tools):
    @tools.tool("look_beats", {"properties": {**ITEM, **WAV, **TRACK, **DETAIL,
        "stems": {"type": "boolean", "default": False, "description": "List the onsets of every stem, not just the mix."},
        "beats_per_bar": {"type": "integer", "description": "For the downbeat guess. Default: the document's."},
        "division": {"type": "integer", "default": 4, "description": "Grid to measure onsets against: 4 = sixteenth notes, 2 = eighths, 1 = beats."},
        "tolerance": {"type": "number", "default": 0.04, "description": "Seconds an onset may sit off the grid."}}})
    def look_beats(ctx, args):
        """Tempo, the beat grid and a downbeat guess, each onset's distance in ms from the nearest beat or sixteenth, against the audio's own beats and the document's tempo map, with a waveform picture. On a render the tempo is the document's, checked against the audio: the reply says whether the audio's beats fit it (a groove also repeats at half, double, 2/3 and 3/2 of its tempo, so a reading from the sound alone, `heard_bpm`, can name a related tempo). With `wav` (no document) the tempo is the audio's own, and a close call names the other reading."""
        doc, wav, stems = _source(ctx, args, "look_music (what: beats)")
        src = _pick(stems, args["track"], "look_music (what: beats)") if args.get("track") else wav
        use_doc = not args.get("wav")
        y, sr = load(src)
        written = B.written_bpm(doc.data, len(y) / sr) if use_doc else None
        r = engine_ears.beats(src, args.get("beats_per_bar") or int(doc.data.get("beatsPerBar", 4)), written)
        div, tol = args.get("division", 4), args.get("tolerance", 0.04) * 1000
        sources = {args["track"]: src} if args.get("track") else {"mix": wav, **(stems if args.get("stems") else {})}
        audio_pos = B.audio_grid(r["beats_s"]) if len(r["beats_s"]) >= 2 else None
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
        r["onsets"], r["document_bpm"] = out, written
        changes = use_doc and len(tempo.segments(doc.data)) > 1
        if use_doc:
            r["audio_vs_document"] = "fits" if B.fits(r, written) else B.relation(r["bpm"], written)
            r["heard_vs_document"] = B.relation(r["heard_bpm"], written)
            r["document_tempo_changes"] = changes
        r["beats_s"], r["downbeats_s"] = _cap(r["beats_s"], args, 80), _cap(r["downbeats_s"], args, 40)
        main = next(iter(out.values()))
        s = (main.get("against_document_tempo") or main.get("against_audio_beats") or {}).get("summary")
        said = B.tempo_line(r, written, changes)
        said += f"; {main['onsets']} onsets" + (f", median {s['median_abs_off_ms']} ms off the {s['grid']} grid, {s['within_limit_pct']:.0f}% within {tol:.0f} ms, leaning {s['lean']}" if s else "")
        return Reply(said + ".", r, [str(png)], [str(png)])

    @tools.tool("look_pitch", {"properties": {**ITEM, **WAV, **TRACK, **DETAIL,
        "fmin": {"type": "number", "description": "Lowest pitch to look for, Hz (default: from the written notes, else 65)."},
        "fmax": {"type": "number", "description": "Highest pitch, Hz (default: from the written notes, else 1500)."},
        "cents_tolerance": {"type": "number", "default": 25, "description": "Cents a note may be off before it is out of tune."},
        "timing_tolerance": {"type": "number", "default": 0.06, "description": "Seconds a note may start early or late."}}})
    def look_pitch(ctx, args):
        """The pitch of one melodic line as notes with times and cents off (vibrato, drift, tuning); with a track, each written note checked for wrong note, wrong octave, late, out of tune or missing. A track that plays several notes at once (chords, a melody over its chords) is checked note by note instead: each written note of each chord looked for in the sound (ok, missing, or wrong octave when only the octave above is there); timing and tuning are judged only on one-voice parts. A picture of the curve over a note grid with the written notes as bars and a dot per written note."""
        doc, wav, stems = _source(ctx, args, "look_music (what: pitch)")
        tid = args.get("track")
        src = _pick(stems, tid, "look_music (what: pitch)") if tid else wav
        written = written_notes(doc.data, [tid]) if tid else []
        lo = min((m for w in written for m in w["midis"]), default=None)
        hi = max((m for w in written for m in w["midis"]), default=None)
        fmin = args.get("fmin") or (float(np.clip(440 * 2 ** ((lo - 12 - 69) / 12), 40, 2000)) if lo is not None else 65.0)
        fmax = args.get("fmax") or (float(np.clip(440 * 2 ** ((hi + 12 - 69) / 12), 80, 4000)) if hi is not None else 1500.0)
        t, midi, frame_s, found = engine_ears.pitch(src, fmin, fmax)
        heard = P.describe_notes(t, midi, frame_s, found)
        r = {"notes": _cap(heard, args, 60), "notes_total": len(heard), "tuning_offset_cents": P.tuning_offset(heard),
             "vibrato_notes": [n["note"] + f"@{n['start']}" for n in heard if n["vibrato"]],
             "drifting_notes": [f"{n['note']}@{n['start']} ({n['drift_cents']:+g} cents)" for n in heard if n["drift_cents"] and abs(n["drift_cents"]) >= 25],
             "range_hz": [round(fmin), round(fmax)]}
        rows = None
        chords = bool(written) and CH.polyphonic(written)
        if written:
            cmp = CH.check(src, written) if chords else P.compare(written, heard, args.get("cents_tolerance", 25), args.get("timing_tolerance", 0.06))
            rows = cmp["rows"]
            r["comparison"] = {**cmp, "rows": rows if args.get("detail") == "full" else [x for x in rows if x["status"] != "ok"][:60]}
        png = ctx.app.state.look_dir(doc.item_id) / f"{Path(src).stem}-pitch.png"
        pitch_picture(png, t, midi, written, rows)
        said = f"{len(heard)} notes heard" + (f"; the line sits {r['tuning_offset_cents']:+g} cents from equal temperament" if heard else "")
        said += f"; vibrato on {len(r['vibrato_notes'])}, drift on {len(r['drifting_notes'])}"
        if chords:
            said = (f"{tid} plays chords: each of its {len(rows)} written notes looked for in the sound: "
                    + ", ".join(f"{n} {k.replace('_', ' ')}" for k, n in r["comparison"]["counts"].items())
                    + "".join([f"; {x['status'].replace('_', ' ')}: {x['written']} at {x['start_s']:g} s" + (f" (heard {x['heard']})" if x.get("heard") else "")
                               for x in rows if x["status"] != "ok"][:8])
                    + ". Timing and tuning are judged only on one-voice parts (the pitch line follows the loudest note)")
        elif rows is not None:
            said += f". Against {len(written)} written notes: " + ", ".join(f"{n} {k.replace('_', ' ')}" for k, n in r["comparison"]["counts"].items())
        elif not tid:
            said += ". No track given, so nothing to compare with (pitch of the mix follows its loudest line)"
        return Reply(said + ".", r, [str(png)], [str(png)])

    @tools.tool("look_clash", {"properties": {**ITEM, **DETAIL,
        "tracks": {"type": "array", "items": {"type": "string"}, "description": "Only these tracks' stems (up to 12; default all, or the 12 loudest when there are more)."},
        "within_db": {"type": "number", "default": 6, "description": "Two stems clash where both are loud and within this many dB of each other."},
        "floor_db": {"type": "number", "description": "Band level (dB, a full-scale sine is about -3) under which a stem doesn't count as there. Default: 40 dB under the loudest band of the stems, so the count doesn't change when the whole mix gets louder."},
        "min_over_db": {"type": "number", "default": 3, "description": "Report only where one stem stands at least this many dB over the other (a part buried by this much). Parts at the same level in a band are not a problem."},
        "min_length": {"type": "number", "default": 0.3, "description": "Shortest clash to report, seconds."}}})
    def look_clash(ctx, args):
        """Where one stem buries another: both loud in the same frequency band at the same time and one stands at least 3 dB (min_over_db) over the other. Spans (start, end, band in Hz, the two tracks, buried_track, buried_by_db, how many dB each stands over the other) ranked by how far one is buried, and a time × band picture coloured by pair. Parts at the same level are not reported: an empty list means no real problem. Needs the last render's stems."""
        doc, _, stems = _source(ctx, args, "look_sound (what: clash)")
        if not stems:
            raise RostrumError(codes.NOT_FOUND, "look_sound (what: clash)", "stems", "were not rendered", hint="render_mix with stems: true.")
        want, left_out = args.get("tracks"), []
        if want and len(want) > C.MAX_STEMS:
            raise RostrumError(codes.BAD_ARGUMENT, "look_sound (what: clash)", f"{len(want)} tracks", f"is more than the {C.MAX_STEMS} the clash finder reads at once",
                               hint="Split them over two calls, or leave `tracks` out to read the loudest ones.")
        if not want:
            want = C.loudest(stems) if len(stems) > C.MAX_STEMS else list(stems)
            left_out = [t for t in stems if t not in want]
        levels, hop = C.stem_levels({t: _pick(stems, t, "look_sound (what: clash)") for t in want})
        floor = args["floor_db"] if "floor_db" in args else C.floor_for(levels)
        spans, maps = C.find_clashes(levels, args.get("within_db", 6), floor, args.get("min_length", 0.3), hop, args.get("min_over_db", C.MIN_OVER_DB))
        png = ctx.app.state.look_dir(doc.item_id) / "clash.png"
        clash_picture(png, maps, spans, hop)
        r = {"clashes": _cap(spans, args, 30), "total": len(spans), "tracks": list(levels), "within_db": args.get("within_db", 6),
             "floor_db": round(floor, 1), "min_over_db": args.get("min_over_db", C.MIN_OVER_DB), "left_out_quietest": left_out,
             "verdict": "one part buries another in the spans listed" if spans else "no real problem: no part stands over another in a band where both matter",
             "note": "a clash is both stems loud in one band with one standing at least min_over_db over the other; `<a>_over_<b>_db` > 0 means a stands over b by that much (b is the one buried, `buried_track`)"}
        said = (f"{len(spans)} clashes among {len(levels)} tracks; worst: {C.line(spans[0])}." if spans
                else f"No real problem among {len(levels)} tracks: no part stands {r['min_over_db']:g} dB or more over another in a band where both are loud.")
        return Reply(said, r, [str(png)], [str(png)])

    @tools.tool("inspect_harmony", {"properties": {**ITEM, **WAV, **TRACK, **DETAIL,
        "source": {"type": "string", "enum": ["auto", "notes", "audio"], "default": "auto", "description": "auto: the document's notes when it has any, else the audio's chroma."},
        "per": {"type": "string", "enum": ["bar", "beat"], "default": "bar"},
        "key": {"type": "string", "description": "Check notes against this key (\"D minor\") instead of the document's key map or the estimate."},
        "checks": {"type": "boolean", "default": True, "description": "Voicing checks on the written notes: range, low close intervals, crossings, wide spacing, out of key."}}})
    def inspect_harmony(ctx, args):
        """Key (from the document's key map, its notes or the audio), the chord per bar or beat, and voicing checks as plain facts: notes outside the instrument's range, close intervals too low, voices crossing, upper voices over an octave apart, notes out of key. Reads the written notes when there are any, so it works before any render (check the harmony, then render); only `source: "audio"`, a `wav`, or a song with no notes reads a render (the voicing checks need notes)."""
        doc = ctx.document(args.get("item"))
        tid = args.get("track")
        notes = written_notes(doc.data, [tid] if tid else None)
        use_notes = args.get("source", "auto") == "notes" or (args.get("source", "auto") == "auto" and notes and not args.get("wav"))
        per = args.get("per", "bar")
        r: dict = {"source": "notes" if use_notes else "audio", "document_keys": [k.get("key") for k in doc.data.get("keys", [])]}
        warnings, chroma = [], None
        if use_notes:
            if not notes:
                raise RostrumError(codes.NOT_FOUND, "look_music (what: harmony)", "notes", "none written in the document" + (f" for track {tid}" if tid else ""))
            end = max(n["end"] for n in notes)
            est = H.key_from_notes(notes)
            rows = H.chart_from_notes(notes, H.windows(doc.data, end, per), H.speller(doc.data, args.get("key"), est))
        else:
            try:
                _, wav, stems = _source(ctx, args, "look_music (what: harmony)")
            except RostrumError as e:                 # nothing written and nothing rendered: say what harmony reads
                if args.get("source", "auto") != "auto" or args.get("wav"):
                    raise
                raise RostrumError(codes.NOT_FOUND, "look_music (what: harmony)", "notes", "none written yet" + (f" on track {tid}" if tid else "")
                                   + ", and no render to hear", hint="Harmony reads the written notes, no render needed: write the notes "
                                   "(run_script), then ask again. Or render_mix to read the audio.") from e
            src = _pick(stems, tid, "look_music (what: harmony)") if tid else wav
            chroma, ct = H.chroma_of(src)
            y, sr = load(src)
            est = engine_ears.key_of_audio(src)        # the engine's key: the one source for audio (ears/engine_ears.py)
            rows = H.chart_from_audio(chroma, ct, H.windows(doc.data, len(y) / sr, per), H.speller(doc.data, args.get("key"), est))
        r["key_estimate"], r["chords"] = est, rows
        declared = H.declared_key(doc.data, args.get("key"))      # the key asked for, else the song's own: never second-guessed by the notes
        used = declared or est["key"] or None
        r["key_declared"], r["key_used_for_checks"] = declared, used
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
            found = [*V.range_problems(notes, ranges), *V.stack_problems(notes), *V.crossings(notes), *V.out_of_key(notes, {**doc.data, "keys": []} if args.get("key") else doc.data, used)]
            found.sort(key=lambda e: e["at_s"])
            r["checks"] = {"problems": _cap(found, {**args, "detail": args.get("detail")}, 40), "total": len(found),
                           "counts": {k: sum(e["kind"] == k for e in found) for k in sorted({e["kind"] for e in found})},
                           "range_unchecked": unchecked, "low_interval_limits": "common orchestration chart, simplified (ears/theory.py LOW_LIMIT)"}
        bars = [x for x in rows if x["beat"] == 1] if per == "beat" else rows
        r["progression"] = " | ".join(x["chord"] for x in bars[:32]) + (" …" if len(bars) > 32 else "")
        said = ("Read from the written notes (no render needed). " if use_notes else "Read from the audio of the last render. " if not args.get("wav") else "Read from the audio file. ")
        said += f"Key {H.key_line(est, r['source'], declared, bool(args.get('key')))}" + (f", checked against {used}" if use_notes else "")
        said += f". Chords: {r['progression']}."
        if "checks" in r:
            c = r["checks"]["counts"]
            said += " Checks: " + (", ".join(f"{n} {k.replace('_', ' ')}" for k, n in c.items()) if c else "no problems found") + "."
            said += _out_of_key_line(found)
        return Reply(said, r, warnings=warnings)

