"""How agents hear (CONVENTIONS § 9): the listen tools on the last render (or any WAV). Each answers facts and,
where a picture helps, a PNG the agent sees at once. They never change the document."""
from __future__ import annotations

import math
from pathlib import Path

from rostrum_core import RostrumError, codes
from rostrum_core.mcp import Reply, Tools

from .. import listen
from ..doc.times import seconds
from ..handoff import LIMITER_SLACK_DB

ITEM = {"item": {"type": "string", "description": "The Sound document's item id. Optional when only one is open."}}
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


def _limiter_inputs(ctx, doc):
    """What the limiter look needs from the last render: the stems that add up to the mix (the tracks that feed
    it directly, plus its bus stems), and a caveat when the glue or master effects also changed the mix."""
    try:
        r = ctx.app.state.last_render(doc.item_id, "look_sound (what: loudness)")
    except RostrumError:
        return None
    direct = r.get("direct") or list(r["stems"])
    stems = {k: r["stems"][k] for k in direct if k in r["stems"]} | dict(r.get("busStems") or {})
    m = r.get("master") or {}
    if not stems:
        return None
    caveat = ("the glue compressor or master effects also acted, so this includes their change"
              if m.get("glueMaxReductionDb", 0) > LIMITER_SLACK_DB or m.get("insertsOnMix") else "")
    return {"stems": stems, "caveat": caveat, "engine_max_db": m.get("limiterMaxReductionDb")}


def _resolve(doc, t, where):
    """A time for a look: seconds, {"beat": n} or "#marker", as the document resolves it."""
    return seconds(t, doc.data, where)


def register(tools: Tools):
    @tools.tool("look_loudness", {"properties": {**ITEM, **WAV}})
    def look_loudness(ctx, args):
        """Integrated loudness (LUFS), true peak, loudness range, the short-term loudness curve and every clipped moment, with a curve picture. On a render's mix it also shows where the master limiter turned the sound down (a curve in the picture, the worst moments with the dB reduced) and which tracks drove each moment, measured from the stems (an estimate, close to the engine's own gain)."""
        doc, wav, _ = _source(ctx, args, "look_sound (what: loudness)")
        png = ctx.app.state.look_dir(doc.item_id) / f"{Path(wav).stem}-loudness.png"
        lim = None if args.get("wav") else _limiter_inputs(ctx, doc)
        r = listen.loudness(wav, out_png=str(png), limiter=lim)
        clips = r.get("clip_moments", [])
        said = f"{r['integrated_lufs']:.1f} LUFS, true peak {r['true_peak_dbtp']:.1f} dBTP, range {r['lra_lu']:.1f} LU, {len(clips)} clipped moments."
        if "limiter" in r:
            w = r["limiter"]["worst"]
            said += (f" Limiter: up to {r['limiter']['max_db']:.1f} dB down for {r['limiter']['seconds_working']:.1f} s"
                     + (f"; worst at {w[0]['time_s']:.2f} s, driven by {', '.join(d['track'] for d in w[0]['drivers'][:3])}." if w else "."))
        return Reply(said, r, [r["png"]], [r["png"]])

    @tools.tool("look_levels", {"properties": {**ITEM}})
    def look_levels(ctx, args):
        """Each track's level from its stem (last render): LUFS, peak, file format, how far under the loudest and the mix (db_vs_mix), and the track's volume now in dB (volume_db); flags buried tracks. To move a track N dB against the other tracks, set its volume to volume_db + N ({"db": …}): the master's loudness target turns every stem up or down together, so the gaps between tracks you set stay. A float stem above 0 dBFS is held, not clipped (flag "over full scale", clips false); only a fixed-point stem at full scale "clips"."""
        doc, wav, stems = _source(ctx, args, "look_sound (what: levels)")
        if not stems:
            raise RostrumError(codes.NOT_FOUND, "look_sound (what: levels)", "stems", "were not rendered", hint="render_mix with stems: true.")
        r = listen.levels(stems, mix=wav)
        gains = {t["id"]: t.get("volume", 1) for t in doc.data.get("tracks", [])}
        for k, row in r["stems"].items():
            g = gains.get(k)
            row["volume_db"] = round(20 * math.log10(g), 1) if isinstance(g, (int, float)) and g > 0 else None
        return Reply(_levels_line(r), r)

    @tools.tool("look_events", {"properties": {**ITEM, **WAV,
        "track": {"type": "string", "description": "Read one track's stem instead of the mix."},
        "expect": {"type": "array", "description": "Times the sounds should start at: seconds, {\"beat\": n} or \"#marker\"."},
        "tolerance": {"type": "number", "default": 0.04, "description": "Seconds a sound may be off (one frame at 25 fps = 0.04)."},
        "by_stem": {"type": "boolean", "default": False, "description": "With expect: for each time, which track's stem starts nearest it (and the next two), how far off, and the mix's nearest onset: one call for every marker."},
        "detail": {"type": "string", "enum": ["short", "full"], "default": "short", "description": "short lists the first 40 onsets; full lists all."}}})
    def look_events(ctx, args):
        """Where sounds start (onsets). With expect, each expected time's nearest onset, how early or late, pass or fail. With expect and by_stem, which track hits each time (all stems of the last render, plus the mix's nearest onset)."""
        doc, wav, stems = _source(ctx, args, "look_music (what: events)")
        if args.get("by_stem"):
            if not args.get("expect"):
                raise RostrumError(codes.BAD_ARGUMENT, "look_music (what: events)", "by_stem", "needs expect", hint="Give expect: times or #markers.")
            if not stems:
                raise RostrumError(codes.NOT_FOUND, "look_music (what: events)", "stems", "were not rendered", hint="render_mix with stems: true.")
            tol = args.get("tolerance", 0.04)
            expect = [_resolve(doc, t, f"look_music (what: events) › expect[{i}]") for i, t in enumerate(args["expect"])]
            r = listen.which_stem(wav, stems, expect, tol)
            for row, name in zip(r["expected"], args["expect"]):
                row["at"] = name
            ok = sum(row["pass"] for row in r["expected"])
            return Reply(f"{ok} of {len(expect)} expected times have a stem starting within {tol * 1000:.0f} ms: "
                         + "; ".join(f"{row['at']} → {row['stem']} ({row['offset_ms']:+.0f} ms)" for row in r["expected"] if row["stem"]) + ".", r)
        if args.get("track"):
            if args["track"] not in stems:
                raise RostrumError.not_found("look_events", "stem", args["track"], stems, "the last render's stems")
            wav = stems[args["track"]]
        expect = [_resolve(doc, t, f"look_music (what: events) › expect[{i}]") for i, t in enumerate(args.get("expect") or [])] or None
        r = listen.onsets(wav, expect=expect, tolerance=args.get("tolerance", 0.04))
        if args.get("detail", "short") == "short" and len(r["onsets_s"]) > 40:
            r = {**r, "onsets_s": r["onsets_s"][:40], "onsets_total": len(r["onsets_s"])}
        if expect:
            bad = [e for e in r["expected"] if not e["pass"]]
            line = f"{len(expect) - len(bad)} of {len(expect)} expected sounds within {args.get('tolerance', 0.04) * 1000:.0f} ms."
        else:
            line = f"{len(r['onsets_s'])} onsets."
        return Reply(line, r)

    @tools.tool("look_spectrum", {"properties": {**ITEM, **WAV,
        "track": {"type": "string", "description": "One track's stem instead of the mix."},
        "marks": {"type": "object", "description": "Labels to draw at times: {\"hit\": 12.5, \"drop\": \"#drop\"}."},
        "start": {"type": "number"}, "end": {"type": "number"}}})
    def look_spectrum(ctx, args):
        """A spectrogram picture (time and frequency labelled, marks drawn), the steady tones in it (held notes, with their note names) and which of those are hum (flat level, on two or more multiples of 50 or 60 Hz together: a lone held note is never hum)."""
        doc, wav, stems = _source(ctx, args, "look_sound (what: spectrum)")
        if args.get("track"):
            wav = stems.get(args["track"]) or wav
        marks = {k: _resolve(doc, v, f"look_sound (what: spectrum) › marks.{k}") for k, v in (args.get("marks") or {}).items()} or None
        rng = (args["start"], args["end"]) if "start" in args and "end" in args else None
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
        """Each track's share of energy under 150 Hz and 60 Hz and in the low mids (150–500 Hz, where parts piling up sound muddy), from the last render's stems, and the same for the whole mix; flags boomy tracks."""
        _, wav, stems = _source(ctx, args, "look_sound (what: low_end)")
        r = listen.low_end(stems or wav, mix=wav if stems else None)
        each = ", ".join(f"{k} {v['low_end_pct']:.0f}% / {v['low_mid_pct']:.0f}%" for k, v in r["tracks"].items())
        flags = "; ".join(f["detail"] + f" ({f['track']})" for f in r["flags"]) or "none"
        return Reply(f"Under 150 Hz / 150–500 Hz: {each}. Flagged: {flags}.", r)


def _levels_line(r: dict) -> str:
    each = ", ".join(f"{k} {v['db_vs_mix']:+.1f} dB (volume {v['volume_db']:+.1f} dB)" if v.get("volume_db") is not None
                     else f"{k} {v['db_vs_mix']:+.1f} dB" for k, v in r["stems"].items())
    flags = "; ".join(f"{f['stem']} {f['flag']}" for f in r["flags"]) or "none"
    return f"{len(r['stems'])} stems against a {r['mix_lufs']:.1f} LUFS mix: {each}. Flags: {flags} (details in data.flags)."
