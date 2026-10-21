"""render_mix: the document compiled to the engine contract and rendered (always a job). One request gives
the mix, every track's stem and every track's meters, written as the item's next versioned render
(`renders/<item>/vNNN/` with its manifest, handoff.py), so the Editor and the project list see it. A render with
solo / mute is a listening check: it goes to `renders/<item>/check/` (replaced each time), never a version."""
from __future__ import annotations

from rostrum_core.mcp import Reply, Tools

from .. import handoff
from ..compile import compile as compile_doc
from ..doc import ops_mix

ITEM = {"item": {"type": "string", "description": "The Sound document's item id. Optional when only one is open."}}


def summary(r: dict) -> str:
    quiet = sorted(r["tracks"], key=lambda t: t["lufs"])[:1]
    q = f" Quietest track: {quiet[0]['id']} at {quiet[0]['lufs']:.1f} LUFS." if quiet else ""
    return (f"Rendered {r['seconds']:.1f} s in {r['renderSeconds']:.1f} s: {r['lufs']:.1f} LUFS, true peak {r['truePeak']:.1f} dBTP, "
            f"{len(r['tracks'])} tracks, {len(r['stems'])} stems" + (f" + {len(r['busStems'])} bus stems" if r.get("busStems") else "")
            + f".{q}")


def register(tools: Tools):
    @tools.tool("render_mix", {"properties": {**ITEM,
        "solo": {"type": "array", "items": {"type": "string"}, "description": "Only these track ids are heard."},
        "mute": {"type": "array", "items": {"type": "string"}, "description": "These track ids are not heard."},
        "master": {"type": "boolean", "default": True, "description": "False: the mix before mastering (no loudness target, glue or master effects)."},
        "stems": {"type": "boolean", "default": True, "description": "Also write one WAV per track and one per bus (`<bus>.bus.wav`)."}}})
    def render_mix(ctx, args):
        """Render the document to a WAV (and stems) as its next version (renders/<item>/vNNN/), with loudness, true
        peak and per-track meters. Returns a job."""
        doc = ctx.document(args.get("item"))
        item = doc.item_id
        master = args.get("master", True)
        follow = ops_mix.follow_calls(doc.data)     # project markers renamed elsewhere: one recorded step first
        if follow:
            doc.apply(follow, ctx.who, label="Follow renamed markers")
        schedule = compile_doc(doc.data, solo=args.get("solo"), mute=args.get("mute"), master=master)
        state = ctx.app.state
        stems = "all" if args.get("stems", True) else []
        who = f"{ctx.who.kind}:{ctx.who.name}"
        partial = bool(args.get("solo") or args.get("mute"))

        def work(job):
            job.progress(note="rendering")
            if partial:     # a listening check, not the item's sound: never a version the Editor could pick up
                out = state.renders(item) / "check" / "check.wav"
                r = state.engine.request("render", schedule=schedule, out=str(out), stems=stems,
                                         stemsDir=str(out.parent / "stems"))
            else:
                r = handoff.render(state.folder, doc, state.engine, schedule, who, stems=stems, master=master)
            state.remember(item, r)
            files = [r["file"], *r["stems"].values(), *r.get("busStems", {}).values()]
            return Reply(summary(r), {**{k: r[k] for k in ("version", "folder") if k in r}, **{k: r[k] for k in ("file", "seconds", "renderSeconds", "lufs", "truePeak", "peak", "lra", "clipped", "tracks", "stems", "busStems", "direct", "ducks")}}, files)

        return ctx.job(f"render {item}", work, key=f"render:{item}:{hash(str(schedule))}")
