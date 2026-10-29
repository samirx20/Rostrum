"""How agents hear (CONVENTIONS § 9): the listen tools on the last render (or any WAV). Each answers facts and,
where a picture helps, a PNG the agent sees at once. They never change the document."""
from __future__ import annotations

import math
from pathlib import Path

from rostrum_core import RostrumError, codes
from rostrum_core.mcp import Reply, Tools

from .. import listen, roles
from ..doc.markers import seconds_of
from ..doc.times import seconds
from ..ears.written import instrument_spec
from ..listen import fault_shape
from ..listen.faults import check as fault_check
from ..listen.loudness import loudest_line
from . import start_level
from .moments_arg import EXPECT, parse as parse_expect

ITEM = {"item": {"type": "string", "description": "The Sound document's item id. Optional when only one is open."}}
WINDOW = {"start": {"type": ["number", "string", "object"], "description": "Read only from here (seconds, {\"beat\": n} or \"#marker\"); needs end."},
          "end": {"type": ["number", "string", "object"], "description": "Read only to here (same forms as start)."}}
WAV = {"wav": {"type": "string", "description": "A WAV to read instead of the last render's mix (absolute path)."}}


def _source(ctx, args, where):
    """(item, mix wav, stems {id: wav}) for a look: the given WAV, or the last render."""
    doc = ctx.document(args.get("item"))
    if args.get("wav"):
        wav = Path(args["wav"])
        if not wav.is_file():
            raise RostrumError(codes.NOT_FOUND, where, f'"{wav}"', "is not a file")
        return doc, str(wav), {}
    r = ctx.app.state.last_render(doc.item_id, where)
    return doc, r["file"], r["stems"]


def _window(doc, args, where):
    """(from_s, to_s) of a `start` / `end` asked for, as the document resolves them, else None. One rule for every look that takes them."""
    if "start" not in args and "end" not in args:
        return None
    if "start" not in args or "end" not in args:
        raise RostrumError(codes.BAD_ARGUMENT, where, "start / end", "need both", hint="Give start and end together, or neither for the whole file.")
    a, b = _resolve(doc, args["start"], f"{where} › start"), _resolve(doc, args["end"], f"{where} › end")
    if b <= a:
        raise RostrumError(codes.BAD_ARGUMENT, where, f"end {b:g} s", f"is not after start {a:g} s")
    return a, b


def _section_spans(doc) -> list[tuple[str, float, float]]:
    """[(name, start s, end s)] of the song's sections (their times as the document resolves them), by start."""
    rows = []
    for sec in doc.data.get("sections", []):
        try:
            rows.append((sec.get("name") or sec["id"], seconds_of(doc.data, sec["at"]), seconds_of(doc.data, sec["end"])))
        except (KeyError, ValueError):
            continue                    # a section whose time no longer resolves is the checks' business, not a look's
    return sorted(rows, key=lambda r: r[1])


def _limiter_inputs(ctx, doc):
    """What the limiter look needs from the last render: the engine's reduction curve, and the stems that add up to the
    mix (the tracks that feed it directly, plus its bus stems) to name who drove it."""
    try:
        r = ctx.app.state.last_render(doc.item_id, "look_sound (what: loudness)")
    except RostrumError:
        return None
    reduction = (r.get("series") or {}).get("reductionDb")
    if not reduction:                    # no mastering stage, or a render from an older engine
        return None
    direct = r.get("direct") or list(r.get("stems") or {})
    stems = {k: r["stems"][k] for k in direct if k in (r.get("stems") or {})} | dict(r.get("busStems") or {})
    m = r.get("master") or {}
    only = m.get("onMixOnly") or []
    caveat = f"the drivers are the tracks as they reach the master, before its {', '.join(only)}" if only else ""
    mm = (doc.data.get("master") or [{}])[0]               # the document's master: Most limiting (maxLimit) applies while Gentle limiting is on
    return {"stems": stems, "reduction": reduction, "caveat": caveat, "engine_max_db": m.get("limiterMaxReductionDb"), "tracks": r.get("tracks"),
            "max_limit_db": mm.get("maxLimit", 2) if mm.get("gentle") else None}


def _resolve(doc, t, where):
    """A time for a look: seconds, {"beat": n} or "#marker", as the document resolves it."""
    return seconds(t, doc.data, where)


def register(tools: Tools):
    @tools.tool("look_loudness", {"properties": {**ITEM, **WAV, **WINDOW, **EXPECT}})
    def look_loudness(ctx, args):
        """With start and end (seconds, beats or #markers) only that stretch is measured (the engine's limiter curve is of the whole file, so it is left out). Integrated loudness (LUFS), true peak, loudness range, the loudest moment and its time (the loudest 3 s and 0.4 s windows, where they start and end, and the highest sample with its time: data.loudest), the short-term loudness curve and every clipped moment, with a curve picture. On a render's mix it also shows where the master's glue and limiter turned the sound down (the engine's own gain curve in the picture, the worst moments with the dB reduced) and, with stems, which tracks drove each moment and which one to turn down by how many dB (data.limiter.advice). Also `ending` (data.ending, in the summary): the level of the last 0.5 s, whether it is still above -50 dBFS (not finished), whether the file is cut off (the last 50 ms fall faster than the fade before them) and the audible end (data.ending.audible_end_s: where the sound falls under -60 dBFS for good, so "it rings out by 52 s" can be checked). For the whole song with sections, the loudness of each section (data.sections: name, from_s, to_s, integrated_lufs, true_peak_dbtp; in the summary), so "the build is louder than the verse" is a number. Room for speech (data.speech_room, in the summary): how many dB a voice at the mix's own loudness would stand over the music in the 1–4 kHz bands where words are understood (a standard speech spectrum, ANSI S3.5, against the mix band by band, weighted by each band's importance to speech; per band in data.speech_room.bands). Under a voice-over aim for +6 dB or more: carve the music there (a pad's low-pass lower, an EQ dip at 2–4 kHz), not its overall level. Band edges: data.band_edges_hz. Faults (data.faults, each {kind, at_s, measured, words}; first in the summary): what a listener would complain about, with the time, the number and what to change: one harmony held 12 s or more with little level movement (heard as one flat tone), a dull top end (4–16 kHz against 250 Hz–1 kHz under -20 dB even in the brightest tenth of the piece), a top end that did not grow into a climax or lift (under +6 dB from the start), a near-mono mix (left/right correlation over 0.9; the fix for a mono source: chorus with spread 1, tremolo with stereo above 0 or a stereo reverb, not width), a hit the master's limiter squashed 3 dB or more (on a render; the fix is a longer loud moment and a build 4–6 dB under the ceiling, not a louder build), a mix it squashes over 3 dB where one part carries 60 % or more of the signal, or over 6 dB on a dense mix (squashed_mix: the quiet parts up, sustained parts where thin, the driving part tamed, then a lower target), and with `expect` moments ({"at": 31.5, "kind": "hit"}) whether each comes across: a weak hit or stop (its ~21 ms attack in the finished file under 2.5x a normal note, or not among the 3 strongest; drums coming back under 2x), with its bright attack (2 kHz up), its strength against the notes of the 2 s before its loudness jump over the 1.5 s before and its contrast with the 2 s before (dB over, its peak over the bed's; 12 dB and 10 dB: it jumps out, not weak), and the fix those numbers point to (a bright transient on it, silence or a duck before it, shorter bed notes into it; headroom first when the build already peaks at the ceiling), the build into a hit or climax already at the ceiling (its peak in the 3 s before within 1.5 dB of the file's), a blurred stop (with the level after against the 2 s before and how much of the bass and kick's pulse goes on), drums dropping early, drums still heard in a drop's gap (their part over 4 kHz under 14 dB below the 2 s before, up to the drop's end or its drums-back entry), a weak climax downbeat, a climax that holds under 3 s, the loudest moment over 3 s after the climax or 0.5 s before it, a lift under +2 LU, a busy speech band in a voice span, a hit the bars around it bury (buried_hit: the bars after it under 7 LU below the hit, or the near silence the brief asks after it under 27 LU below). Replies open NOT DONE: with each fault (id, when, fix) or DONE:; on the whole last render the faults also include loudness more than 0.5 LU off the master target (loudness), a duck under a voice dipping under 3 dB (duck:<track>), a marker named for a moment with nothing starting within 30 ms (marker_onset:<marker>) and sound above -50 dBFS after the song's end (rings_past_end); render_mix refuses open faults unless keep: {id: why} explains them. "No faults found" means none of these, not that the music is good."""
        doc, wav, _ = _source(ctx, args, "look_sound (what: loudness)")
        png = ctx.app.state.look_dir(doc.item_id) / f"{Path(wav).stem}-loudness.png"
        lim = None if args.get("wav") else _limiter_inputs(ctx, doc)
        win = _window(doc, args, "look_sound (what: loudness)")
        r = listen.loudness(wav, out_png=str(png), limiter=lim, range=win)
        _, _, moments = parse_expect(doc, args.get("expect"), "look_sound (what: loudness)")
        f = fault_check(wav, moments, r.get("limiter"), whole=win is None, song={"tracks": lim["tracks"], "data": doc.data} if lim else None, data=doc.data)
        r["faults"] = f["faults"]
        clips = r.get("clip_moments", [])
        said = f["words"] + " "
        said += f"{r['integrated_lufs']:.1f} LUFS, true peak {r['true_peak_dbtp']:.1f} dBTP, range {r['lra_lu']:.1f} LU, {len(clips)} clipped moments. "
        said += loudest_line(r["loudest"])
        if r.get("ending"):
            said += " " + r["ending"]["words"]
        if win is None and not args.get("wav") and (spans := _section_spans(doc)):
            r["sections"] = listen.by_section(wav, spans)
            said += " By section: " + "; ".join(f"{s['name']} {s['integrated_lufs']:.1f}" if s["integrated_lufs"] is not None
                                                 else f"{s['name']} silent" for s in r["sections"]) + " LUFS."
        said += f" {r['speech_room']['words']}."
        if "limiter" in r:
            w = r["limiter"]["worst"]
            said += (f" Limiter: up to {r['limiter']['max_db']:.1f} dB down for {r['limiter']['seconds_working']:.1f} s"
                     + (f"; worst at {w[0]['time_s']:.2f} s" + (f", driven by {', '.join(d['track'] for d in w[0]['drivers'][:3])}" if w[0]["drivers"] else "") + "." if w else ".")
                     if r["limiter"]["seconds_working"] else " Limiter: not working.")
            if r["limiter"].get("advice"):
                said += " " + r["limiter"]["advice"]["words"]
        return Reply(said, r, [r["png"]], [r["png"]], faults=_faults(ctx, doc, args, wav, f["faults"], win, r["integrated_lufs"]))

    @tools.tool("look_levels", {"properties": {**ITEM}})
    def look_levels(ctx, args):
        """Each track's level from its stem (last render): LUFS, peak, file format, how far under the loudest and the mix (db_vs_mix), and the track's volume now in dB against the instrument's starting level (volume_db, start_level_db when the engine gives it), the stem's energy in the 1–4 kHz speech region against the mix's (speech_1_4k_db_vs_mix: which tracks fill the region a voice needs), the mix's room for speech (data.speech_room, in the summary: dB a voice at the mix's loudness stands over the music in 1–4 kHz; aim for +6 or more under a voice-over), and the render reply's per-track lufs before the master's gain (lufs_before_master: levels' lufs is the stem as written, after the master's gain, so the two differ by that gain); says which track sets the master limiter and by how many dB to lower it (data.limiter_advice); flags buried tracks. To move a track N dB against the other tracks, set its volume to volume_db + N ({"db": …}): the master's loudness target and limiter turn every stem up or down together, so the gaps between tracks you set stay. A float stem above 0 dBFS is held, not clipped (flag "over full scale", clips false); only a fixed-point stem at full scale "clips"."""
        doc, wav, stems = _source(ctx, args, "look_sound (what: levels)")
        if not stems:
            raise RostrumError(codes.NOT_FOUND, "look_sound (what: levels)", "stems", "were not rendered", hint="render_mix with stems: true.")
        r = listen.levels(stems, mix=wav)
        render = ctx.app.state.last_render(doc.item_id, "look_sound (what: levels)")
        before = {t["id"]: t.get("lufs") for t in render.get("tracks") or []}
        described = ctx.app.state.engine.request("describe")
        gains = {t["id"]: t.get("volume", 1) for t in doc.data.get("tracks", [])}
        for k, row in r["stems"].items():
            g = gains.get(k)
            row["volume_db"] = round(20 * math.log10(g), 1) if isinstance(g, (int, float)) and g > 0 else None
            row["start_level_db"] = start_level.of(described, instrument_spec(doc.data, k))
            if isinstance(before.get(k), (int, float)) and before[k] > -70:
                row["lufs_before_master"] = round(before[k], 1)
        gain = (render.get("master") or {}).get("gainDb")
        r["note"] += ("; lufs is the integrated, gated (BS.1770) loudness of the stem file as written, which carries the master's gain "
                      + (f"({gain:+.1f} dB on the mix)" if isinstance(gain, (int, float)) else "") + "; lufs_before_master is the render reply's per-track figure, "
                      "measured before that gain: the two differ by the master's gain, they are not two windows. volume_db is against the "
                      "instrument's starting level (0 = as the engine levelled it).")
        lim = _limiter_inputs(ctx, doc)
        if lim and not args.get("wav"):
            from ..listen.limiter import limiter as measure
            m = measure(lim["stems"], lim["reduction"], lim["caveat"], engine_max_db=lim["engine_max_db"], max_limit_db=lim["max_limit_db"])
            r["limiter_advice"] = m["advice"]
        return Reply(_levels_line(r), r)

    @tools.tool("look_events", {"properties": {**ITEM, **WAV,
        "track": {"type": "string", "description": "Read one track's stem instead of the mix."},
        **EXPECT,
        "tolerance": {"type": "number", "default": 0.04, "description": "Seconds a sound may be off (one frame at 25 fps = 0.04)."},
        "by_stem": {"type": "boolean", "default": False, "description": "With expect: for each time, which track's stem starts nearest it (and the next two), how far off, and the mix's nearest onset: one call for every marker."},
        "detail": {"type": "string", "enum": ["short", "full"], "default": "short", "description": "short lists the first 40 onsets; full lists all."}}})
    def look_events(ctx, args):
        """Where sounds start (onsets). With expect, each expected time's nearest onset (within 250 ms: a sound starting farther off is not quoted as that time's), how early or late, pass or fail; a soft or masked start (a swell, an entry over a held chord) is found as the level rising 6 dB over its quietest just before. Passing the time is not enough: give a moment's kind ({"at": 31.5, "kind": "hit"}, also stop, drop, climax, lift, entry, voice) and the faults (data.faults, in the summary) say whether it comes across, with the time, the measured number and what to change (a weak hit: "1.0x a normal note, bright attack 1.0x, silence before it", with the fix those numbers point to; a blurred stop; drums dropping 0.7 s early; drums still heard in a drop's gap; a climax that holds only 2 s; the build at the ceiling before a hit). With expect and by_stem, which track hits each time (all stems of the last render, plus the mix's nearest onset); a stem with no start within 250 ms of a time is not listed for it."""
        doc, wav, stems = _source(ctx, args, "look_music (what: events)")
        if args.get("by_stem"):
            if not args.get("expect"):
                raise RostrumError(codes.BAD_ARGUMENT, "look_music (what: events)", "by_stem", "needs expect", hint="Give expect: times or #markers.")
            if not stems:
                raise RostrumError(codes.NOT_FOUND, "look_music (what: events)", "stems", "were not rendered", hint="render_mix with stems: true.")
            tol = args.get("tolerance", 0.04)
            expect, labels, _ = parse_expect(doc, args["expect"], "look_music (what: events)")
            r = listen.which_stem(wav, stems, expect, tol)
            for row, name in zip(r["expected"], labels):
                row["at"] = name
            ok = sum(row["pass"] for row in r["expected"])
            return Reply(f"{ok} of {len(expect)} expected times have a stem starting within {tol * 1000:.0f} ms: "
                         + "; ".join(f"{row['at']} → {row['stem']} ({row['offset_ms']:+.0f} ms)" for row in r["expected"] if row["stem"]) + ".", r)
        if args.get("track"):
            if args["track"] not in stems:
                raise RostrumError.not_found("look_events", "stem", args["track"], stems, "the last render's stems")
            wav = stems[args["track"]]
        expect, _, moments = parse_expect(doc, args.get("expect"), "look_music (what: events)")
        r = listen.onsets(wav, expect=expect or None, tolerance=args.get("tolerance", 0.04))
        if args.get("detail", "short") == "short" and len(r["onsets_s"]) > 40:
            r = {**r, "onsets_s": r["onsets_s"][:40], "onsets_total": len(r["onsets_s"])}
        if expect:
            bad = [e for e in r["expected"] if not e["pass"]]
            line = f"{len(expect) - len(bad)} of {len(expect)} expected sounds within {args.get('tolerance', 0.04) * 1000:.0f} ms."
        else:
            line = f"{len(r['onsets_s'])} onsets."
        if moments:
            f = fault_check(wav, moments, whole=False, data=doc.data)
            r["faults"] = f["faults"]
            line += " " + f["words"]
        return Reply(line, r, faults=fault_shape.shape(f["faults"], doc) if moments else None)

    @tools.tool("look_spectrum", {"properties": {**ITEM, **WAV,
        "track": {"type": "string", "description": "One track's stem instead of the mix."},
        "marks": {"type": "object", "description": "Labels to draw at times: {\"hit\": 12.5, \"drop\": \"#drop\"}."},
        **WINDOW}})
    def look_spectrum(ctx, args):
        """A spectrogram picture (time and frequency labelled, marks drawn), the steady tones in it (held notes, with their note names) and which of those are hum (flat level, on two or more multiples of 50 or 60 Hz together: a lone held note is never hum)."""
        doc, wav, stems = _source(ctx, args, "look_sound (what: spectrum)")
        if args.get("track"):
            wav = stems.get(args["track"]) or wav
        marks = {k: _resolve(doc, v, f"look_sound (what: spectrum) › marks.{k}") for k, v in (args.get("marks") or {}).items()} or None
        rng = _window(doc, args, "look_sound (what: spectrum)")
        png = ctx.app.state.look_dir(doc.item_id) / f"{Path(wav).stem}-spectrum.png"
        r = listen.spectrogram(wav, str(png), marks=marks, range=rng)
        hum = r.get("hum_lines", [])
        held = [t for t in r.get("tones", []) if not t["is_hum"]]
        said = f"{len(hum)} hum lines" + (f" (lowest {min(h['freq_hz'] for h in hum):.0f} Hz)" if hum else "")
        said += f"; {len(held)} held tones (" + ", ".join(t["note"] for t in held[:6]) + ")" if held else ""
        return Reply(f"Spectrogram written; {said}.", r, [r["png"]], [r["png"]])

    @tools.tool("look_stereo", {"properties": {**ITEM, **WAV, "section": {"type": "number", "default": 5}}})
    def look_stereo(ctx, args):
        """Left/right balance and stereo correlation per section, with mono-compatibility warnings."""
        _, wav, _ = _source(ctx, args, "look_sound (what: stereo)")
        r = listen.stereo(wav, sections_s=args.get("section", 5))
        return Reply(f"{len(r.get('mono_warnings', []))} mono warnings over {len(r.get('sections', []))} sections.", r)

    @tools.tool("look_low_end", {"properties": {**ITEM}})
    def look_low_end(ctx, args):
        """Each track's share of energy under 150 Hz and 60 Hz and in the low mids (150–500 Hz, where parts piling up sound muddy), from the last render's stems, and the same for the whole mix; flags boomy tracks (over 50 % under 150 Hz; for a bass or drum part 90 %, since the low end is its job)."""
        doc, wav, stems = _source(ctx, args, "look_sound (what: low_end)")
        low = {t for t in stems if _is_low_part(doc, t)}
        r = listen.low_end(stems or wav, mix=wav if stems else None, low_roles=low)
        each = ", ".join(f"{k} {v['low_end_pct']:.0f}% / {v['low_mid_pct']:.0f}%" for k, v in r["tracks"].items())
        flags = "; ".join(f["detail"] + f" ({f['track']})" for f in r["flags"]) or "none"
        return Reply(f"Under 150 Hz / 150–500 Hz: {each}. Flagged: {flags}.", r)


def _faults(ctx, doc, args, wav, found, win, lufs):
    """look_sound (loudness)'s shared faults: the listening faults, and (on the whole last render) loudness against the
    master's target, ducks under a voice and sound past the song's end."""
    if win is not None or args.get("wav"):
        return fault_shape.shape(found, doc)
    master = (doc.data.get("master") or [{}])[0]
    try:
        last = ctx.app.state.last_render(doc.item_id, "look_sound")
    except RostrumError:
        last = {}
    return fault_shape.all_faults(doc, found, wav, lufs, master.get("loudness", -16) if master.get("normalize") else None,
                                  last.get("ducks"), last.get("stems"))


def _is_low_part(doc, track_id: str) -> bool:
    """A bass or a drum kit: a part whose job is the low end (roles.py), so a high share under 150 Hz is its job, not a boom."""
    spec = instrument_spec(doc.data, track_id)
    role = roles.ROLES.get(roles.key(spec)) if spec else None
    return bool(role and {"bass", "groove"} & set(role.parts))


def _levels_line(r: dict) -> str:
    each = ", ".join(f"{k} {v['db_vs_mix']:+.1f} dB (volume {start_level.words(v['volume_db'], v.get('start_level_db'))}; 1–4 kHz {v['speech_1_4k_db_vs_mix']:+.1f} dB)"
                     if v.get("volume_db") is not None else f"{k} {v['db_vs_mix']:+.1f} dB" for k, v in r["stems"].items())
    flags = "; ".join(f"{f['stem']} {f['flag']}" for f in r["flags"]) or "none"
    return f"{len(r['stems'])} stems against a {r['mix_lufs']:.1f} LUFS mix: {each}. Flags: {flags} (details in data.flags). {r['speech_room']['words']}." + (" " + r["limiter_advice"]["words"] if r.get("limiter_advice") else "")
