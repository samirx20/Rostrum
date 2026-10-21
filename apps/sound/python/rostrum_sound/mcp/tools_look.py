"""How agents hear (CONVENTIONS § 9): the listen tools on the last render (or any WAV). Each answers facts and,
where a picture helps, a PNG the agent sees at once. They never change the document."""
from __future__ import annotations

from pathlib import Path

from rostrum_core import RostrumError, codes
from rostrum_core.mcp import Reply, Tools

from .. import listen
from ..doc.times import seconds

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


def _resolve(doc, t, where):
    """A time for a look: seconds, {"beat": n} or "#marker", as the document resolves it."""
    return seconds(t, doc.data, where)


def register(tools: Tools):
    @tools.tool("look_loudness", {"properties": {**ITEM, **WAV}})
    def look_loudness(ctx, args):
        """Integrated loudness (LUFS), true peak, loudness range, the short-term loudness curve and every clipped moment, with a curve picture."""
        doc, wav, _ = _source(ctx, args, "look_loudness")
        png = ctx.app.state.look_dir(doc.item_id) / f"{Path(wav).stem}-loudness.png"
        r = listen.loudness(wav, out_png=str(png))
        clips = r.get("clip_moments", [])
        return Reply(f"{r['integrated_lufs']:.1f} LUFS, true peak {r['true_peak_dbtp']:.1f} dBTP, range {r['lra_lu']:.1f} LU, {len(clips)} clipped moments.",
                     r, [r["png"]], [r["png"]])

    @tools.tool("look_levels", {"properties": {**ITEM}})
    def look_levels(ctx, args):
        """Each track's level from its stem (last render): LUFS, peak, how far under the loudest and the mix; flags buried tracks."""
        _, wav, stems = _source(ctx, args, "look_levels")
        if not stems:
            raise RostrumError(codes.NOT_FOUND, "look_levels", "stems", "were not rendered", hint="render_mix with stems: true.")
        r = listen.levels(stems, mix=wav)
        return Reply(_levels_line(r), r)

    @tools.tool("look_events", {"properties": {**ITEM, **WAV,
        "track": {"type": "string", "description": "Read one track's stem instead of the mix."},
        "expect": {"type": "array", "description": "Times the sounds should start at: seconds, {\"beat\": n} or \"#marker\"."},
        "tolerance": {"type": "number", "default": 0.04, "description": "Seconds a sound may be off (one frame at 25 fps = 0.04)."},
        "detail": {"type": "string", "enum": ["short", "full"], "default": "short", "description": "short lists the first 40 onsets; full lists all."}}})
    def look_events(ctx, args):
        """Where sounds start (onsets). With expect, each expected time's nearest onset, how early or late, pass or fail."""
        doc, wav, stems = _source(ctx, args, "look_events")
        if args.get("track"):
            if args["track"] not in stems:
                raise RostrumError.not_found("look_events", "stem", args["track"], stems, "the last render's stems")
            wav = stems[args["track"]]
        expect = [_resolve(doc, t, f"look_events › expect[{i}]") for i, t in enumerate(args.get("expect") or [])] or None
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
        """A spectrogram picture (time and frequency labelled, marks drawn) and any steady hum lines found."""
        doc, wav, stems = _source(ctx, args, "look_spectrum")
        if args.get("track"):
            wav = stems.get(args["track"]) or wav
        marks = {k: _resolve(doc, v, f"look_spectrum › marks.{k}") for k, v in (args.get("marks") or {}).items()} or None
        rng = (args["start"], args["end"]) if "start" in args and "end" in args else None
        png = ctx.app.state.look_dir(doc.item_id) / f"{Path(wav).stem}-spectrum.png"
        r = listen.spectrogram(wav, str(png), marks=marks, range=rng)
        hum = r.get("hum_lines", [])
        return Reply(f"Spectrogram written; {len(hum)} steady hum lines" + (f" (lowest {hum[0]['freq_hz']:.0f} Hz)." if hum else "."), r, [r["png"]], [r["png"]])

    @tools.tool("look_stereo", {"properties": {**ITEM, **WAV, "section": {"type": "number", "default": 5}}})
    def look_stereo(ctx, args):
        """Left/right balance and stereo correlation per section, with mono-compatibility warnings."""
        _, wav, _ = _source(ctx, args, "look_stereo")
        r = listen.stereo(wav, sections_s=args.get("section", 5))
        return Reply(f"{len(r.get('mono_warnings', []))} mono warnings over {len(r.get('sections', []))} sections.", r)

    @tools.tool("look_low_end", {"properties": {**ITEM}})
    def look_low_end(ctx, args):
        """Each track's share of energy under 150 Hz and 60 Hz (from the last render's stems); flags boomy tracks."""
        _, wav, stems = _source(ctx, args, "look_low_end")
        r = listen.low_end(stems or wav)
        return Reply(f"{len(r['tracks'])} measured; flagged: {'; '.join(map(str, r['flags'])) or 'none'}.", r)


def _levels_line(r: dict) -> str:
    return f"{len(r['stems'])} stems measured against a {r['mix_lufs']:.1f} LUFS mix; flags: {'; '.join(map(str, r['flags'])) or 'none'}."
