"""MIDI files: edit_import_midi puts a .mid into the document (one change, one undo step); render_mix (what: midi) writes the
document's notes, hits, sustain / expression / bend lanes, tempo map, keys, markers and sections as `renders/<item>/midi/<item>.mid` (a job, as every
render_* tool). What MIDI can't carry (a drum key the kit lacks, a drum with no GM key) comes back as a
warning, never dropped quietly."""
from __future__ import annotations

from rostrum_core.mcp import Reply, Tools

from .. import midi
from ..doc import markers

ITEM = {"item": {"type": "string", "description": "The Sound document's item id. Optional when only one is open."}}


def register(tools: Tools):
    @tools.tool("edit_import_midi", {"required": ["path"], "properties": {**ITEM,
        "path": {"type": "string", "description": "The .mid file (absolute path)."},
        "song_map": {"type": "boolean", "default": True, "description": "Also take the file's tempo map, time "
                     "signature and key changes (replacing the document's). False: only tracks, markers, sections."}}})
    def edit_import_midi(ctx, args):
        """Import a MIDI file: one track per MIDI track (notes in beats on a built-in instrument picked from the GM
        program; channel 10 as drum hits on the drum kit; the sustain pedal CC 64, expression CC 11, mod wheel CC 1
        and pitch wheel as the track's sustain / dynamics / vibrato / bend lanes, RPN 0 as its bendRange), its markers, cue-point sections and (song_map) tempo map
        and keys. One change in the history. Then set each new track's instrument with track.set."""
        doc = ctx.document(args.get("item"))
        before = {t["id"] for t in doc.data.get("tracks", [])}
        with markers.project(getattr(doc, "folder", None)):          # the project's markers are known: none is made twice
            calls, skipped = midi.import_calls(doc.data, args["path"], args.get("song_map", True))
        change = ctx.apply(doc, calls, "Import MIDI")
        new = [t["id"] for t in doc.data.get("tracks", []) if t["id"] not in before]
        notes = sum(len(doc.item(t).get("notes", [])) + len(doc.item(t).get("hits", [])) for t in new)
        changed = {"seq": change.seq, "ops": sorted({c["op"] for c in calls}), "group": ctx.group} if change else None
        return Reply(f"Imported {args['path']}: {len(new)} tracks ({', '.join(new) or 'none'}), {notes} notes and hits"
                     + (f"; {len(skipped)} things skipped (see warnings)." if skipped else "."),
                     {"tracks": new, "seq": doc.seq}, warnings=skipped, changed=changed)

    @tools.tool("render_midi", {"properties": {**ITEM,
        "path": {"type": "string", "description": "Where to write the .mid; left out = renders/<item>/midi/<item>.mid."}}})
    def render_midi(ctx, args):
        """Write the document as a MIDI file (format 1): every track's notes and drum hits (channel 10), its sustain,
        dynamics, vibrato and bend lanes (CC 64, CC 11, CC 1, the pitch wheel; bendRange as RPN 0), the tempo
        map, time signature, key changes, markers, and sections as cue points. Returns a job."""
        doc = ctx.document(args.get("item"))
        item, root = doc.item_id, doc.data
        out = args.get("path") or str(ctx.app.state.renders(item) / "midi" / f"{item}.mid")

        def work(job):
            skipped = midi.export(root, out)
            return Reply(f"Wrote {out}" + (f"; {len(skipped)} things skipped (see warnings)." if skipped else "."),
                         {"file": out}, [out], warnings=skipped)

        return ctx.job(f"midi {item}", work, key=f"midi:{item}:{doc.seq}:{out}")
