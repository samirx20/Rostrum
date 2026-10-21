"""render_mix: the document compiled to the engine contract and rendered (always a job). One request gives
the mix, every track's stem and every track's meters."""
from __future__ import annotations

from rostrum_core.mcp import Reply, Tools

from ..compile import compile as compile_doc

ITEM = {"item": {"type": "string", "description": "The Sound document's item id. Optional when only one is open."}}


def summary(r: dict) -> str:
    quiet = sorted(r["tracks"], key=lambda t: t["lufs"])[:1]
    q = f" Quietest track: {quiet[0]['id']} at {quiet[0]['lufs']:.1f} LUFS." if quiet else ""
    return (f"Rendered {r['seconds']:.1f} s in {r['renderSeconds']:.1f} s: {r['lufs']:.1f} LUFS, true peak {r['truePeak']:.1f} dBTP, "
            f"{len(r['tracks'])} tracks, {len(r['stems'])} stems.{q}")


def register(tools: Tools):
    @tools.tool("render_mix", {"properties": {**ITEM,
        "solo": {"type": "array", "items": {"type": "string"}, "description": "Only these track ids are heard."},
        "mute": {"type": "array", "items": {"type": "string"}, "description": "These track ids are not heard."},
        "master": {"type": "boolean", "default": True, "description": "False: the mix before mastering (no loudness target, glue or master effects)."},
        "stems": {"type": "boolean", "default": True, "description": "Also write one WAV per track."},
        "name": {"type": "string", "default": "mix", "description": "File name (no extension) under the project's renders/<item>/."}}})
    def render_mix(ctx, args):
        """Render the document to a WAV (and stems), with loudness, true peak and per-track meters. Returns a job."""
        doc = ctx.document(args.get("item"))
        item = doc.item_id
        schedule = compile_doc(doc.data, solo=args.get("solo"), mute=args.get("mute"), master=args.get("master", True))
        state = ctx.app.state
        out = state.renders(item) / f"{args.get('name', 'mix')}.wav"
        stems = "all" if args.get("stems", True) else []

        def work(job):
            job.progress(note="rendering")
            r = state.engine.request("render", schedule=schedule, out=str(out), stems=stems, stemsDir=str(out.with_suffix("")) + "-stems")
            state.remember(item, r)
            files = [r["file"], *r["stems"].values()]
            return Reply(summary(r), {k: r[k] for k in ("file", "seconds", "renderSeconds", "lufs", "truePeak", "peak", "lra", "clipped", "tracks", "stems", "ducks")}, files)

        return ctx.job(f"render {item}", work, key=f"render:{item}:{hash(str(schedule))}")
