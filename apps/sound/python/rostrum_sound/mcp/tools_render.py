"""render_mix: the document compiled to the engine contract and rendered (always a job). One request gives
the mix, every track's stem and every track's meters, written as the item's next versioned render
(`renders/<item>/vNNN/` with its manifest, handoff.py), so the Editor and the project list see it. A render with
solo / mute is a listening check: it goes to `renders/<item>/check/` (replaced each time), never a version."""
from __future__ import annotations

import shutil
from pathlib import Path

from rostrum_core import RostrumError, codes
from rostrum_core.mcp import Reply, Tools
from rostrum_core.mcp import faults as shared_faults

from .. import deliver, handoff, packs, presets
from ..compile import compile as compile_doc
from ..doc import markers, ops_mix, times
from .. import fit_loudness as fit
from ..listen import applied, fault_shape, squash, static_part, weakest
from ..listen.faults import check as fault_check
from . import asked_keep, brief_keep, export_target, pending_edits, session_clock, stop_limiter, tools_fit
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


def asked_moments(doc, expect) -> list[dict]:
    """The moments a finished render is checked against: `expect` when given, else the song's markers named for one
    ("hit", "drums back", "climax", listen/weakest.py)."""
    if expect:
        return parse_expect(doc, expect, "render_mix")[2]
    return weakest.from_markers(markers.all(doc.data))


def weakest_words(wav, moments, limiter=None, peaky=None, found=None) -> tuple[str, list[str]]:
    """The reply's weakest-moments lines; a file the ears cannot read is said, not hidden (the render itself stands).
    `found`: fault_check's faults when already measured (not measured twice)."""
    try:
        said = weakest.words(wav, moments, limiter, peaky, found)
    except RostrumError as e:
        return f"The listening check could not read the mix: {e}", []
    return said, [ln.split(". ", 1)[1] for ln in said.splitlines()[1:]]


def deliver_checked(state, item, r, found, keep, copied) -> None:
    """faults.deliver on the file that is delivered (the copy in `folder` when there is one, else the render's own file,
    whose new name is written back so the looks that follow read it)."""
    target = copied[0] if copied else r["file"]
    try:
        shared_faults.deliver(found, keep, "render_mix", target)
    except RostrumError:
        if not copied:
            r["file"] = str(Path(r["file"]).with_name(f"{Path(r['file']).stem}.NOT-DONE{Path(r['file']).suffix}"))
            state.remember(item, r)
        raise


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
        "format": {"type": "string", "enum": [f["id"] for f in deliver.FORMATS] + list(deliver.ALIASES), "default": deliver.DEFAULT_FORMAT,
                   "description": "; ".join(f"{f['id']}: {f['label']} — {f['detail']}" for f in deliver.FORMATS) + "; wav: the same as wav24. Every file of the render is in this format."},
        "sampleRate": {"type": "integer", "enum": [r["id"] for r in deliver.RATES],
                       "description": "Hz: 44100 (music), 48000 (video), 96000 (high resolution; not for mp3). Default: the document's rate."},
        "trim": {"type": "boolean", "default": True, "description": "Trim the silent end: the mix and every stem stop at the music's last audible sound (above -80 dBFS) plus a short tail, all the same length. False: the song's full length."},
        "from": {"description": "Only a part of the song: where the file starts (seconds, a beat or a marker, like any time). Needs `to`. The engine renders the part itself, mastered and measured on its own, so the loudness is the part's; the silent end is trimmed only if `trim` is on."},
        "to": {"description": "Where the part ends (a time). Needs `from`."},
        "name": {"type": "string", "description": "The mix file's name without its type (\"Launch theme\" -> Launch theme.wav), as the Export sheet's name field. Default: <item>_mix. Characters a file name can't hold are replaced; stems keep their track names. Not for a listening check (solo / mute)."},
        "folder": {"type": "string", "description": "An absolute folder path (made when it is not there): the finished mix, under `name`, is also copied there (and the stems, in a folder beside it called \"<name> stems\"), so the file lands where you want it with no shell copy. The render stays in the project's renders/ as its next version; the reply's `copied` lists the new files."},
        **{"expect": {**EXPECT["expect"], "description": EXPECT["expect"]["description"] + " The finished reply lists the three weakest of them "
                      "(time, what is weak, the measured number, the first fix). Default: the song's markers named hit, stop, drums out, drums back, climax or lift."}},
        "keep": {**shared_faults.KEEP["keep"], "description": "Faults you leave on purpose: {fault_id: \"why\"}, ids as the reply's faults name them. "
                 "Each why quotes the brief where it asks for that fault (in quotes, or 3+ of its words in a row); the brief is stored with "
                 "brief(\"...\") in the script. No brief, or a why that does not quote it: the keep is refused and the fault's fix says why."},
        "ring_past_length": {"anyOf": [{"type": "boolean"}, {"type": "number", "minimum": 0, "maximum": deliver.MOST_RING_S}], "default": False,
                             "description": f"False (default): when the song has a length the file is exactly that long: trim never cuts below it, and a ring-out that would run past it is faded out inside it (the reply says by how much). True: the file may run on up to {deliver.RING_S:g} s past the length (the usual delivery allowance) while the ring-out dies away, faded inside that; a number: up to that many seconds (at most {deliver.MOST_RING_S:g})."}}})
    def render_mix(ctx, args):
        """Render the document to a file (24-bit WAV by default; `format` picks WAV 16 / 24 / 32-bit float, FLAC or MP3) and stems as its next version (renders/<item>/vNNN/), with loudness, true
        peak and per-track meters. Stems are named after their tracks; the manifest maps ids to files. Recorded instruments are played from installed sample packs (a missing one stops the render and names the pack: run_model_install). A render that used a CC-BY instrument (Salamander piano, Wurlitzer, Rhodes, the rock kit) answers `credits`, the lines to credit it with, and the manifest holds them.
        A render whose master has a loudness target lands on it within 0.5 LU: the song is measured first and, when gentle limiting (`maxLimit`, 2 dB by default) would leave it under, the file is rendered with the limit raised as far as the target needs (at most 6 dB, so hits keep their attack, or the song's own maxLimit when higher; the song keeps its own maxLimit, so playback stays transparent). The reply says how far the limit went and how many dB of limiting it took (data.loudness.pushed); when that is short, the loudness fault names the fix (tame_peaks, trim_track or a lower target). The render waits for edit jobs on the song asked before it (edit_loudness, cleanup, voice), so their edits are in the file (a wait over 300 s fails the render, naming the job). This file is for checking and delivery: 2D's render_video does not use it, it renders the song's current document itself (cached while the song is unchanged), so a video's sound always follows the song, not the last render_mix.
        Loudness (data.loudness, in the summary): what the previous render predicted this one would measure (predicted_lufs), what it measured (measured_lufs) and the limiting it took (limiting_db). Over ~3 dB of limiting starts to flatten acoustic drums and piano: for acoustic music prefer edit_loudness tame_peaks. The file is exactly the song's length when it has one (trim never cuts below it; a ring-out running past it is faded out inside it: `ring_past_length` true lets it run on up to 2 s). `folder` also copies the mix there under `name`. The finished reply lists the three weakest moments of the mastered mix against the asked moments (`expect`, else the song's markers named hit / stop / drums out / drums back / climax / lift), one line each with the time, what is weak, the measured numbers and the first fix (data.weakest; the same check as look_sound / look_music faults: a hit's attack against a normal note and the bed before it), then asks for a fix pass and says the time and passes left. Replies open NOT DONE: with each fault (id, when, fix) or DONE:; render_mix (and run_script look with folder) refuses open faults (the file is kept as <name>.NOT-DONE.wav) unless keep: {id: why} explains them, each why quoting the brief's words that ask for that fault (the brief stored with brief("...") in the script; no brief or no quote: refused, the fault's fix says why); a fault on the brief's own moment (its what says so and what passes) can be kept only after a render that named it (a fix was tried) and within the stated distance of passing; else fix it or move the moment in the script. The faults are the listening check's plus: loudness more than 0.5 LU off the master's target (id loudness), a duck under a voice dipping under 3 dB (duck:<track>), a marker named for a moment (hit, stop, drop, climax ...) with no sound starting within 30 ms (marker_onset:<marker>), a true peak over the master's ceiling (true_peak), clipped samples (clipped), and sound above -50 dBFS after the song's end, after the ring ring_past_length allows (rings_past_end), and, when the brief asks for a clean ending or a marker names the end, an ending faded by that ring (faded_end) or a file that stops while still playing (chopped_end); when the brief asks for a quiet start or ending, an opening or ending under 20 LU below the loudest 3 s (loud_opening, loud_ending); and over 3 dB of limiting on an exposed part, or 6 dB on a full mix (squashed_mix: how much, where, which part, the fixes in order); and, before an asked climax (else the loudest 3 s when the brief asks for a build and no lift), a last 3 bars that rise under 1.5 LU while getting neither 1.25x busier nor 4 dB brighter (stall_before_peak: the bars, their numbers and the parts to lift). A part holding one sound at one level for over 16 bars or 24 s in a piece asked to build comes back in warnings (static part). A fault the previous render also named says what the change did (was, now, what passes). Returns a job. The quickest loop is run_script with `look` (true, or these same arguments): the whole piece as one script, rendered and checked in one call; edit the script and run it again."""
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
        if schedule.get("length") is not None:
            with markers.project(getattr(doc, "folder", None)):     # in seconds: the song may write it in beats or bars
                options["length"] = times.seconds(doc.data["length"], doc.data, "length")   # asked = delivered (deliver.py)
            if ring:
                options["ring"] = ring
        target = _target_folder(args.get("folder"))         # a wrong folder answers now, not after the render
        with markers.project(getattr(doc, "folder", None)):          # a time may name a project marker
            moments = [] if partial else asked_moments(doc, args.get("expect"))   # a wrong expect answers now
            for k in ("from", "to"):
                if k in args:
                    options[k] = times.seconds(args[k], doc.data, k)
        deliver.Options.read(options, doc.data.get("sampleRate", 48000))      # a wrong choice answers now, not after the render

        master_now = (doc.data.get("master") or [{}])[0] if master else {}
        try:                                                         # what the last render predicts for this one (the Export sheet's sentence)
            last = state.last_render(item, "render_mix")
        except Exception:  # noqa: BLE001  no render yet: nothing to predict
            last = {}
        before = fit.landing(master_now, last) if master and last else {}
        seen_before = set(last.get("faultIds") or [])      # the faults the previous render named (asked_keep.py)
        numbers_before = last.get("faultNumbers") or {}    # and what they measured (applied.py: what a change did)
        drum_ids = [t["id"] for t in doc.data.get("tracks", []) if t.get("instrument") in ("kit", "kitSfz") or t.get("hits")]

        edits = pending_edits.pending(ctx.jobs, item)          # asked before this render: their edits belong in the file

        def work(job):
            if edits:
                job.progress(note="waiting for the song's edits")
            late = pending_edits.wait(edits, "render_mix")
            fresh = compile_doc(doc.data, solo=args.get("solo"), mute=args.get("mute"), master=master)   # the song as it is now
            goal = (fresh.get("master") or {}).get("loudness")
            master_here = (doc.data.get("master") or [{}])[0] if master else {}
            pushed, at_target = {}, None
            if master and not partial:                       # a named target is reached (export_target.py)
                job.progress(note="measuring against the target")
                pushed, at_target = export_target.push(state, doc, item, options)
            job.progress(note="rendering")
            schedule_now = at_target or fresh
            if partial:     # a listening check, not the item's sound: never a version the Editor could pick up
                out = state.renders(item) / "check" / "check.wav"
                r = state.engine.request("render", schedule=schedule_now, out=str(out), stems="all" if stems == "groups" else stems,
                                         stemsDir=str(out.parent / "stems"))
            else:
                r = handoff.render(state.folder, doc, state.engine, schedule_now, who, stems=stems, master=master, options=options,
                                   markers_file=bool(args.get("markers")), name=args.get("name") or "")
            state.remember(item, r)
            files = [r["file"], *r["stems"].values(), *r.get("busStems", {}).values()]
            copied = _copy_to(target, r, files) if target and not partial else []
            loud = loudness(r, export_target.master_as_rendered(master_here, pushed), {} if pushed else before) if master and not partial else None
            if loud is not None and pushed:
                loud["pushed"] = {k: pushed[k] for k in ("max_limit_db", "was_db", "reaches", "lufs", "limit_db")}
            said = summary(r, goal, loud) + export_target.words(pushed) + "".join(f" {w}" for w in late) + (f" Copied to {copied[0]}" + (f" (and {len(copied) - 1} more)" if len(copied) > 1 else "") + "." if copied else "")
            weak, found, notes = [], None, []
            if not partial:
                job.progress(note="listening")
                limiter, peaky = stop_limiter.read(ctx, doc, r, moments)
                try:
                    raw = fault_check(r["file"], moments, limiter, peaky=peaky, song={"tracks": r.get("tracks"), "data": doc.data},
                                      drums=[r["stems"][i] for i in drum_ids if (r.get("stems") or {}).get(i)])["faults"]
                except RostrumError:                         # the ears cannot read it: weakest_words says so
                    raw = None
                notes = static_part.warnings(doc)              # a part that never moves in a piece asked to build
                heard, weak = weakest_words(r["file"], moments, limiter, peaky, raw)
                said += squash.line(limiter, r.get("tracks"), doc.data)
                said += "\n" + heard + "\n" + session_clock.fix_pass(getattr(state, "clock", None), r.get("renderSeconds"))
                if raw is not None:
                    found = fault_shape.all_faults(doc, raw, r["file"], r.get("lufs"), goal, r.get("ducks"), r.get("stems"),
                                                   ring_s=ring, peak=(r.get("truePeak"), master_here.get("truePeak", -1)), clipped=r.get("clipped"),
                                                   push=(loud or {}).get("push_max_limit"), faded=r.get("fadedEnd"), moments=moments)
                    export_target.fix_when_short(found, pushed)
                    near = asked_keep.mark(raw, found, moments)
                    applied.tell(raw, found, numbers_before)
                    r["faultIds"] = [f["id"] for f in found]
                    r["faultNumbers"] = applied.record(raw, found)
                    state.remember(item, r)
                    if ctx.tool == "render_mix" or copied:   # a delivery; run_script's look without folder is a check, never refused
                        deliver_checked(state, item, r, found, brief_keep.screen(found, asked_keep.screen(found, args.get("keep"), seen_before, near), doc.data), copied)
            return Reply(said, {**({"loudness": loud} if loud else {}), **({"weakest": weak} if weak else {}), **({"copied": copied} if copied else {}), **{k: r[k] for k in ("version", "folder") if k in r}, **{k: r[k] for k in ("file", "seconds", "renderSeconds", "lufs", "truePeak", "peak", "lra", "clipped", "tracks", "stems", "busStems", "direct", "ducks")},
                              **({"credits": packs.credit_lines(r)} if packs.credit_lines(r) else {}),
                              **{k: r[k] for k in ("format", "sampleRate", "songSeconds", "trimmed", "range", "stemsBy", "warnings", "clippedFiles") if k in r}}, files, warnings=notes, faults=found)

        return ctx.job(f"render {item}", work, key=f"render:{item}:{hash(str((schedule, options, args.get('name'), moments, args.get('folder'), args.get('keep'))))}")
