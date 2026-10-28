"""render_mix: the document compiled to the engine contract and rendered (always a job). One request gives
the mix, every track's stem and every track's meters, written as the item's next versioned render
(`renders/<item>/vNNN/` with its manifest, handoff.py), so the Editor and the project list see it. A render with
solo / mute is a listening check: it goes to `renders/<item>/check/` (replaced each time), never a version."""
from __future__ import annotations

import shutil
from pathlib import Path

from rostrum_core import RostrumError, codes
from rostrum_core.mcp import Reply, Tools

from .. import deliver, handoff, packs, presets
from ..compile import compile as compile_doc
from ..doc import markers, ops_mix, times
from .. import fit_loudness as fit
from ..listen import weakest
from . import deliver_hold, session_clock, stop_limiter, tools_fit
from .moments_arg import EXPECT, parse as parse_expect

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


def loudness(r: dict, master: dict | None, before: dict) -> dict:
    """The reply's loudness facts: what the last render predicted (fit_loudness.landing, the Export sheet's sentence), what
    this one measured, and the limiting it took. `before`: landing() of the previous render ({} with none)."""
    m = r.get("master") or {}
    after = fit.landing(master or {}, r)
    out = {"measured_lufs": round(r["lufs"], 2), "limiting_db": round(m.get("limiterMaxReductionDb") or 0, 2)}
    if before:
        out["predicted_lufs"] = before["lufs"]
    if after:
        out |= {"target": after["target"], "need_db": after["need_db"], "max_limit": after["limit"], "reaches": after["reaches"],
                **({"push_max_limit": after["push"]["max_limit_db"]} if after.get("push") else {}), "words": after["words"]}
    return out


def loud_words(l: dict) -> str:
    said = (f" Loudness: predicted {l['predicted_lufs']:.1f} LUFS, measured {l['measured_lufs']:.1f}" if "predicted_lufs" in l
            else f" Loudness: measured {l['measured_lufs']:.1f} LUFS") + f", with {l['limiting_db']:.1f} dB of limiting."
    if "target" in l and not l["reaches"]:
        said += f" {l['words']}" + (f" To reach it: master maxLimit {l['push_max_limit']:g} (edit_loudness keep_balance), or "
                                                f"edit_loudness tame_peaks to keep acoustic drums and piano open." if "push_max_limit" in l
                                      else " Fix: edit_loudness {\"apply\": \"best\"} (edit_loudness keep_balance raises the limiting).")
    elif l["limiting_db"] > fit.LOT_DB:
        said += fit.a_lot(l["limiting_db"])
    return said


def summary(r: dict, goal=None, loud: dict | None = None) -> str:
    credits = packs.credit_lines(r)
    quiet = sorted(r["tracks"], key=lambda t: t["lufs"])[:1]
    q = f" Quietest track: {quiet[0]['id']} at {quiet[0]['lufs']:.1f} LUFS." if quiet else ""
    return (f"Rendered {r['seconds']:.1f} s in {r['renderSeconds']:.1f} s: {r['lufs']:.1f} LUFS, true peak {r['truePeak']:.1f} dBTP, "
            f"{len(r['tracks'])} tracks, {len(r['stems'])} stems" + (f" + {len(r['busStems'])} bus stems" if r.get("busStems") else "")
            + f".{q}" + (loud_words(loud) if loud else held(r, goal)) + (f" Credit these instruments where the sound goes: {'; '.join(credits)}." if credits else "")
            + "".join(f" {w.rstrip('.')}." for w in r.get("warnings") or []))


def _target_folder(folder) -> Path | None:
    """The folder a render is also copied to: absolute, made when missing; a wrong one is refused before anything renders."""
    if not folder:
        return None
    path = Path(folder)
    if not path.is_absolute():
        raise RostrumError(codes.BAD_ARGUMENT, "render_mix", f'folder "{folder}"', "is not an absolute path", hint="Give the whole path, e.g. C:/work/out.")
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise RostrumError(codes.BAD_ARGUMENT, "render_mix", f'folder "{folder}"', f"could not be made ({e.strerror})", hint="Pass a folder you can write to.") from e
    return path


def _copy_to(folder: Path, r: dict, files: list[str]) -> list[str]:
    """Copy the render's mix (and, in a folder beside it, its stems) into `folder`; returns the new paths, the mix first."""
    mix = Path(r["file"])
    out = [shutil.copy2(mix, folder / mix.name)]
    stems = [Path(p) for p in files if Path(p) != mix]
    if stems:
        beside = folder / f"{mix.stem} stems"
        beside.mkdir(exist_ok=True)
        out += [shutil.copy2(p, beside / p.name) for p in stems]
    return [str(Path(p)) for p in out]


def _loud_fix(loud: dict | None) -> str:
    """The change that lands a render on its loudness target, in the words a script and a call use."""
    if loud and loud.get("push_max_limit"):
        m = loud["push_max_limit"]
        return f"raise the master's maxLimit to {m:g} (a script: master(maxLimit={m:g}); or edit_loudness {{\"apply\": \"best\"}})"
    return "edit_loudness {\"apply\": \"best\"} lands it in one measured call"


def asked_moments(doc, expect) -> list[dict]:
    """The moments a finished render is checked against: `expect` when given, else the song's markers named for one
    ("hit", "drums back", "climax", listen/weakest.py)."""
    if expect:
        return parse_expect(doc, expect, "render_mix")[2]
    return weakest.from_markers(markers.all(doc.data))


def weakest_words(wav, moments, limiter=None, peaky=None) -> tuple[str, list[str]]:
    """The reply's weakest-moments lines; a file the ears cannot read is said, not hidden (the render itself stands)."""
    try:
        said = weakest.words(wav, moments, limiter, peaky)
    except RostrumError as e:
        return f"The listening check could not read the mix: {e}", []
    return said, [ln.split(". ", 1)[1] for ln in said.splitlines()[1:]]


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
        "name": {"type": "string", "description": "The mix file's name without its type (\"Launch theme\" -> Launch theme.wav), as the Export sheet's name field. Default: <item>_mix. Characters a file name can't hold are replaced; stems keep their track names. Not for a listening check (solo / mute)."},
        "folder": {"type": "string", "description": "An absolute folder path (made when it is not there): the finished mix, under `name`, is also copied there (and the stems, in a folder beside it called \"<name> stems\"), so the file lands where you want it with no shell copy. The render stays in the project's renders/ as its next version; the reply's `copied` lists the new files."},
        **{"expect": {**EXPECT["expect"], "description": EXPECT["expect"]["description"] + " The finished reply lists the three weakest of them "
                      "(time, what is weak, the measured number, the first fix). Default: the song's markers named hit, stop, drums out, drums back, climax or lift."}},
        "ring_past_length": {"anyOf": [{"type": "boolean"}, {"type": "number", "minimum": 0, "maximum": deliver.MOST_RING_S}], "default": False,
                             "description": f"False (default): when the song has a length the file is exactly that long: trim never cuts below it, and a ring-out that would run past it is faded out inside it (the reply says by how much). True: the file may run on up to {deliver.RING_S:g} s past the length (the usual delivery allowance) while the ring-out dies away, faded inside that; a number: up to that many seconds (at most {deliver.MOST_RING_S:g})."},
        **deliver_hold.KEEP}})
    def render_mix(ctx, args):
        """Render the document to a file (24-bit WAV by default; `format` picks WAV 16 / 24 / 32-bit float, FLAC or MP3) and stems as its next version (renders/<item>/vNNN/), with loudness, true
        peak and per-track meters. Stems are named after their tracks; the manifest maps ids to files. Recorded instruments are played from installed sample packs (a missing one stops the render and names the pack: run_model_install). A render that used a CC-BY instrument (Salamander piano, Wurlitzer, Rhodes, the rock kit) answers `credits`, the lines to credit it with, and the manifest holds them.
        A first render often lands 1 to 3 dB under the master's loudness target (-16 LUFS): gentle limiting holds the mix to `maxLimit` (2 dB) instead of squashing it. The reply says so and edit_loudness {"apply": "best"} (or keep_balance) reaches the target in one measured call; do not leave it quiet. This file is for checking and delivery: 2D's render_video does not use it, it renders the song's current document itself (cached while the song is unchanged), so a video's sound always follows the song, not the last render_mix.
        Loudness (data.loudness, in the summary): what the previous render predicted this one would measure (predicted_lufs), what it measured (measured_lufs) and the limiting it took (limiting_db). With a loudness target that the master's gentle limiting (`maxLimit`, 2 dB by default) cannot reach, it says where the file lands and what reaching the target needs ("Will land at -16.4 LUFS: reaching -14 needs 4.4 dB of limiting"): raise `maxLimit` to push_max_limit (edit_loudness keep_balance; the true-peak ceiling still holds) or keep it dynamic. Over ~3 dB of limiting starts to flatten acoustic drums and piano: for acoustic music prefer edit_loudness tame_peaks. The file is exactly the song's length when it has one (trim never cuts below it; a ring-out running past it is faded out inside it: `ring_past_length` true lets it run on). `folder` also copies the mix there under `name`. The finished reply lists the three weakest moments of the mastered mix against the asked moments (`expect`, else the song's markers named hit / stop / drums out / drums back / climax / lift), one line each with the time, what is weak, the measured numbers and the first fix (data.weakest; the same check as look_sound / look_music faults: a hit's attack against a normal note and the bed before it), then asks for a fix pass and says the time and passes left. Returns a job. The quickest loop is run_script with `look` (true, or these same arguments): the whole piece as one script, rendered and checked in one call; edit the script and run it again."""
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
        ring = deliver.ring_allowed(args.get("ring_past_length"))     # a wrong one answers now
        length_s = None
        if schedule.get("length") is not None:
            with markers.project(getattr(doc, "folder", None)):     # in seconds: the song may write it in beats or bars
                length_s = options["length"] = times.seconds(doc.data["length"], doc.data, "length")   # asked = delivered (deliver.py)
            if ring:
                options["ring"] = ring
        keep = deliver_hold.read_keep(args.get("keep"))            # a wrong keep answers now
        target = _target_folder(args.get("folder"))         # a wrong folder answers now, not after the render
        with markers.project(getattr(doc, "folder", None)):          # a time may name a project marker
            moments = [] if partial else asked_moments(doc, args.get("expect"))   # a wrong expect answers now
            for k in ("from", "to"):
                if k in args:
                    options[k] = times.seconds(args[k], doc.data, k)
        deliver.Options.read(options, doc.data.get("sampleRate", 48000))      # a wrong choice answers now, not after the render

        goal = (schedule.get("master") or {}).get("loudness")       # the target the engine was given (None: no target)
        master_now = (doc.data.get("master") or [{}])[0] if master else {}
        try:                                                         # what the last render predicts for this one (the Export sheet's sentence)
            before = fit.landing(master_now, state.last_render(item, "render_mix")) if master else {}
        except Exception:  # noqa: BLE001  no render yet: nothing to predict
            before = {}

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
            loud = loudness(r, master_now, before) if master and not partial else None
            weak, copied, hold = [], [], {}
            said = summary(r, goal, loud)
            if not partial:
                job.progress(note="listening")
                lim = stop_limiter.read(ctx, doc, r, moments)
                heard, weak = weakest_words(r["file"], moments, *lim)
                found = deliver_hold.open_faults(r, master_now, length_s, ring, _loud_fix(loud), *lim) if master else []
                still, kept = deliver_hold.decide(found, keep)
                hold = {"open_faults": [{k: f[k] for k in ("kind", "at_s", "words")} for f in still], **({"kept": kept} if kept else {})}
                if target and still:       # the delivery waits for a clean check (deliver_hold.py); the render stands
                    said = deliver_hold.held_words(still, str(target)) + "\n" + said
                    hold["delivered"] = False
                elif target:
                    copied = _copy_to(target, r, files)
                    said += (f" Copied to {copied[0]}" + (f" (and {len(copied) - 1} more)" if len(copied) > 1 else "")
                             + ". " + deliver_hold.clean_words(found, kept))
                    hold["delivered"] = True
                else:
                    said += " " + deliver_hold.pending_words(still)
                said += "\n" + heard + "\n" + session_clock.fix_pass(getattr(state, "clock", None), r.get("renderSeconds"))
            return Reply(said, {**hold, **({"loudness": loud} if loud else {}), **({"weakest": weak} if weak else {}), **({"copied": copied} if copied else {}), **{k: r[k] for k in ("version", "folder") if k in r}, **{k: r[k] for k in ("file", "seconds", "renderSeconds", "lufs", "truePeak", "peak", "lra", "clipped", "tracks", "stems", "busStems", "direct", "ducks")},
                              **({"credits": packs.credit_lines(r)} if packs.credit_lines(r) else {}),
                              **{k: r[k] for k in ("format", "sampleRate", "songSeconds", "trimmed", "range", "stemsBy", "warnings", "clippedFiles") if k in r}}, files)

        return ctx.job(f"render {item}", work, key=f"render:{item}:{hash(str((schedule, options, args.get('name'), moments, str(target), keep)))}")
