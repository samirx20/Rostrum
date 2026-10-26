"""render_mix: the document compiled to the engine contract and rendered (always a job). One request gives
the mix, every track's stem and every track's meters, written as the item's next versioned render
(`renders/<item>/vNNN/` with its manifest, handoff.py), so the Editor and the project list see it. A render with
solo / mute is a listening check: it goes to `renders/<item>/check/` (replaced each time), never a version."""
from __future__ import annotations

from rostrum_core.mcp import Reply, Tools

from .. import deliver, handoff, packs, presets
from ..compile import compile as compile_doc
from ..doc import markers, ops_mix, times
from .. import fit_loudness as fit
from . import tools_fit

ITEM = {"item": {"type": "string", "description": "The Sound document's item id. Optional when only one is open."}}


def held(r: dict, goal=None) -> str:
    """The master's gentle limiting, said when it turned the whole mix down (engine `master.heldDb`: how far the mix was
    turned down so the limiter stays within `maxLimit`; `limiterMaxReductionDb`: what the limiter then pulls). The limiter's
    need rises dB for dB with the mix, so reaching the target takes `maxLimit` = what it pulls now + `heldDb`."""
    m = r.get("master") or {}
    h = m.get("heldDb") or 0
    if h < 0.1 or (isinstance(goal, (int, float)) and goal - r["lufs"] < fit.SHORT_OK):
        return ""                               # held a little but on the target (within what the engine settles to)
    pulls = m.get("limiterMaxReductionDb", 0)
    under = f"landed {goal - r['lufs']:.1f} dB under the {goal:g} LUFS target" if isinstance(goal, (int, float)) and goal > r["lufs"] else "was turned down"
    loud = fit.peakiest_track(r) if r.get("tracks") else None
    need = pulls + h
    first = fit.first_choice(need, pulls)        # held down: the limiter pulls what maxLimit allows
    why = {"keep_balance": f"maxLimit {need + 0.05:.1f} keeps the balance, barely more limiting",
           "tame_peaks": f"a gentle compressor on {loud or 'the most peaked track'} (the most peaked), threshold and makeup measured, keeps the balance and the limit"}[first]
    way = (f"call edit_loudness {{\"apply\": \"{first}\"}} (one call, measured by rendering; {why}) instead of setting the limiter or a compressor by hand; "
           f"edit_loudness without apply lists all three ways (keep_balance, tame_peaks, trim_track)")
    return (f" Gentle limiting turned the whole mix down {h:.1f} dB so the limiter pulls at most {pulls:.1f} dB at the loudest moment; "
            f"the mix {under}: {way}.")


def summary(r: dict, goal=None) -> str:
    credits = packs.credit_lines(r)
    quiet = sorted(r["tracks"], key=lambda t: t["lufs"])[:1]
    q = f" Quietest track: {quiet[0]['id']} at {quiet[0]['lufs']:.1f} LUFS." if quiet else ""
    return (f"Rendered {r['seconds']:.1f} s in {r['renderSeconds']:.1f} s: {r['lufs']:.1f} LUFS, true peak {r['truePeak']:.1f} dBTP, "
            f"{len(r['tracks'])} tracks, {len(r['stems'])} stems" + (f" + {len(r['busStems'])} bus stems" if r.get("busStems") else "")
            + f".{q}" + held(r, goal) + (f" Credit these instruments where the sound goes: {'; '.join(credits)}." if credits else "")
            + "".join(f" {w.rstrip('.')}." for w in r.get("warnings") or []))


def register(tools: Tools):
    tools_fit.register(tools)
    @tools.tool("render_mix", {"properties": {**ITEM,
        "solo": {"type": "array", "items": {"type": "string"}, "description": "Only these track ids are heard."},
        "mute": {"type": "array", "items": {"type": "string"}, "description": "These track ids are not heard."},
        "master": {"type": "boolean", "default": True, "description": "False: the mix before mastering (no loudness target, glue or master effects)."},
        "stems": {"enum": [True, False, "all", "groups"], "default": True,
                  "description": "true / \"all\": a file per track (named after the track) and per group (named after the group). \"groups\": a file per group (a bus tracks play into) and per track that is in no group, nothing twice. false: only the mix. "
                                 "Stems carry the master's whole gain (fader, fades, glue, loudness target, limiter: one gain worked out on the mix), so the ungrouped tracks' stems plus the group stems add up to the mix; "
                                 "master effects, master reverb and the safety clip are on the mix only, and the reply's warnings say so (and name any file cut flat at full scale)."},
        "preset": {"enum": list(presets.PRESETS), "description": "; ".join(f"{k}: {v['label']} — {v['detail']}" for k, v in presets.PRESETS.items())
                   + ". Sets format, sampleRate, trim and stems (and writes markers.json) unless you give them."},
        "format": {"type": "string", "enum": [f["id"] for f in deliver.FORMATS], "default": deliver.DEFAULT_FORMAT,
                   "description": "; ".join(f"{f['id']}: {f['label']} — {f['detail']}" for f in deliver.FORMATS) + ". Every file of the render is in this format."},
        "sampleRate": {"type": "integer", "enum": [r["id"] for r in deliver.RATES],
                       "description": "Hz: 44100 (music), 48000 (video), 96000 (high resolution; not for mp3). Default: the document's rate."},
        "trim": {"type": "boolean", "default": True, "description": "Trim the silent end: the mix and every stem stop at the music's last audible sound (above -80 dBFS) plus a short tail, all the same length. False: the song's full length."},
        "from": {"description": "Only a part of the song: where the file starts (seconds, a beat or a marker, like any time). Needs `to`. The engine renders the part itself, mastered and measured on its own, so the loudness is the part's; the silent end is trimmed only if `trim` is on."},
        "to": {"description": "Where the part ends (a time). Needs `from`."},
        "name": {"type": "string", "description": "The mix file's name without its type (\"Launch theme\" -> Launch theme.wav), as the Export sheet's name field. Default: <item>_mix. Characters a file name can't hold are replaced; stems keep their track names. Not for a listening check (solo / mute)."}}})
    def render_mix(ctx, args):
        """Render the document to a file (24-bit WAV by default; `format` picks WAV 16 / 24 / 32-bit float, FLAC or MP3) and stems as its next version (renders/<item>/vNNN/), with loudness, true
        peak and per-track meters. Stems are named after their tracks; the manifest maps ids to files. Recorded instruments are played from installed sample packs (a missing one stops the render and names the pack: run_model_install). A render that used a CC-BY instrument (Salamander piano, Wurlitzer, the rock kit) answers `credits`, the lines to credit it with, and the manifest holds them. Returns a job."""
        doc = ctx.document(args.get("item"))
        args = presets.expand(args, args.get("preset"))             # a wrong preset answers now
        item = doc.item_id
        master = args.get("master", True)
        follow = ops_mix.follow_calls(doc.data)     # project markers renamed elsewhere: one recorded step first
        if follow:
            doc.apply(follow, ctx.who, label="Follow renamed markers")
        schedule = compile_doc(doc.data, solo=args.get("solo"), mute=args.get("mute"), master=master)
        state = ctx.app.state
        stems = {True: "all", False: [], "all": "all", "groups": "groups"}[args.get("stems", True)]
        who = f"{ctx.who.kind}:{ctx.who.name}"
        partial = bool(args.get("solo") or args.get("mute"))
        options = {k: args[k] for k in ("format", "sampleRate", "trim") if k in args}
        with markers.project(getattr(doc, "folder", None)):          # a time may name a project marker
            for k in ("from", "to"):
                if k in args:
                    options[k] = times.seconds(args[k], doc.data, k)
        deliver.Options.read(options, doc.data.get("sampleRate", 48000))      # a wrong choice answers now, not after the render

        goal = (schedule.get("master") or {}).get("loudness")       # the target the engine was given (None: no target)

        def work(job):
            job.progress(note="rendering")
            if partial:     # a listening check, not the item's sound: never a version the Editor could pick up
                out = state.renders(item) / "check" / "check.wav"
                r = state.engine.request("render", schedule=schedule, out=str(out), stems="all" if stems == "groups" else stems,
                                         stemsDir=str(out.parent / "stems"))
            else:
                r = handoff.render(state.folder, doc, state.engine, schedule, who, stems=stems, master=master, options=options,
                                   markers_file=bool(args.get("markers")), name=args.get("name") or "")
            state.remember(item, r)
            files = [r["file"], *r["stems"].values(), *r.get("busStems", {}).values()]
            return Reply(summary(r, goal), {**{k: r[k] for k in ("version", "folder") if k in r}, **{k: r[k] for k in ("file", "seconds", "renderSeconds", "lufs", "truePeak", "peak", "lra", "clipped", "tracks", "stems", "busStems", "direct", "ducks")},
                              **({"credits": packs.credit_lines(r)} if packs.credit_lines(r) else {}),
                              **{k: r[k] for k in ("format", "sampleRate", "songSeconds", "trimmed", "range", "stemsBy", "warnings", "clippedFiles") if k in r}}, files)

        return ctx.job(f"render {item}", work, key=f"render:{item}:{hash(str((schedule, options, args.get('name'))))}")
