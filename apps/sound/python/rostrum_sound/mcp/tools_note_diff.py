"""`inspect_note_changes`: what happened to the notes and drum hits between two states of the song (two history steps,
"before my last N steps", "before the last N steps" or a saved version) and now, per track: added / removed / changed
(pitch or drum, time, length, velocity). Counts first, then one short line per note, capped at `limit`.

    step 41 → now, step 44: 12 added, 3 removed, 5 changed.
    piano: 10 added, 3 removed, 5 changed
      + piano.n9000  9.00 s  bar 5.3  C4  1 beats  vel 0.8
      ~ piano.n4000  4.00 s  bar 3.1  C4→D4, 1→2 beats

Read-only: the states are read from the song's history (Document.at_step), nothing is changed.
"""
from __future__ import annotations

from rostrum_core import RostrumError, codes, formats
from rostrum_core.mcp import Reply, Tools

from ..doc import note_diff as ND
from .tools_notes import _bounds, _where

LIMIT = 30
_SINCE = ('Where to compare from: a history step number (the song right after that step; 0 = the empty start), '
          '{"mine": N} (before your own last N steps), {"steps": N} (before the last N steps, anyone\'s) or '
          '{"version": "name"} (a saved version).')


def state_at(doc, seq: int) -> dict:
    """The song as it stood right after step `seq` (the current data at the newest step), brought up to this build's
    format when a later step upgraded the file (as restoring a version does)."""
    if seq >= doc.seq:
        return doc.data
    data, older = doc.at_step(seq), formats.before(doc.history.changes, seq)
    return doc.kind.bring_up(data, older, doc.folder)[0] if older is not None else data


def since_step(doc, since, who) -> tuple[int, str]:
    """(step, words) for `since` (_SINCE's forms)."""
    h = doc.history
    if isinstance(since, bool) or since is None:
        pass
    elif isinstance(since, int):
        if not 0 <= since <= doc.seq:
            raise RostrumError(codes.BAD_ARGUMENT, "inspect_note_changes", f"since {since}",
                               f"is not a step of this song (0 to {doc.seq})", hint="inspect_history lists the steps.")
        return since, f"step {since}"
    elif isinstance(since, dict) and "version" in since:
        name = since["version"]
        if name not in h.versions:
            raise RostrumError.not_found("inspect_note_changes", "version", name, h.versions)
        return h.versions[name], f'version "{name}" (step {h.versions[name]})'
    elif isinstance(since, dict) and ("mine" in since or "steps" in since):
        n = int(since.get("mine", since.get("steps")))
        if n < 1:
            raise RostrumError(codes.BAD_ARGUMENT, "inspect_note_changes", f"{since}", "must count at least 1 step")
        steps = [c for c in h.changes if "steps" in since or c.who == who][-n:]
        if not steps:
            raise RostrumError(codes.NOT_FOUND, "inspect_note_changes", "your steps", "there are none in this song",
                               hint='Pass {"steps": N} for anyone\'s steps, or a step number.')
        words = "your" if "mine" in since else "the"
        return steps[0].seq - 1, f"before {words} last {len(steps)} step{'s' * (len(steps) != 1)} (step {steps[0].seq - 1})"
    raise RostrumError(codes.BAD_ARGUMENT, "inspect_note_changes", f"since {since!r}", "is not a form it reads", hint=_SINCE)


def _changed(before, after, old, new) -> str:
    said = []
    if old["what"] != new["what"]:
        said.append(f"{old['what']}→{new['what']}")
    if old["start"] != new["start"]:
        said.append(f"moved from {_where(before, old['start'])}")
    if old["length"] != new["length"]:
        said.append(f"{old['length']:.3g}→{new['length']:.3g} beats")
    if old["vel"] != new["vel"]:
        said.append(f"vel {old['vel']:.2g}→{new['vel']:.2g}")
    return ", ".join(said)


def _line(root, mark, i, f) -> str:
    length = f"  {f['length']:.3g} beats" if f["length"] is not None else ""
    return f"  {mark} {i}  {_where(root, f['start'])}  {f['what']}{length}  vel {f['vel']:.2g}"


def words(diff: dict, before: dict, after: dict, limit: int) -> list[str]:
    lines, left = [], limit
    for tid, d in diff.items():
        n = {k: len(v) for k, v in d.items()}
        lines.append(f"{tid}: {n['added']} added, {n['removed']} removed, {n['changed']} changed")
        rows = [_line(after, "+", i, f) for i, f in d["added"]] + [_line(before, "-", i, f) for i, f in d["removed"]] + \
               [f"  ~ {i}  {_where(after, new['start'])}  {'' if old['what'] != new['what'] else new['what'] + '  '}{_changed(before, after, old, new)}" for i, old, new in d["changed"]]
        lines += rows[:left]
        if len(rows) > left:
            lines.append(f"  … {len(rows) - left} more on {tid}")
        left = max(left - len(rows), 0)
    return lines


def register(tools: Tools):
    @tools.tool("inspect_note_changes", {"required": ["since"], "properties": {
        "since": {"description": _SINCE},
        "until": {"type": "integer", "minimum": 0, "description": "A later history step to compare to. Left out = the song now."},
        "track": {"type": "string", "description": "Only this track (its id). Left out = every track."},
        "section": {"type": "string", "description": "Only notes that start in this section (before or after)."},
        "from": {"description": 'Only notes starting from here: a bar {"bar": 5}, seconds, {"beat": 8} or a marker "#drop".'},
        "to": {"description": "…up to here (not included), same forms."},
        "limit": {"type": "integer", "default": LIMIT, "minimum": 1, "maximum": 500, "description": "At most this many note lines."},
        "item": {"type": "string", "description": "The song's item id. Optional when only one is open."}}})
    def inspect_note_changes(ctx, args):
        """What happened to the notes and drum hits between two states of the song, per track: added, removed and changed (pitch or drum, start, length, velocity), counts first, then one line per note (+ added, - removed, ~ changed with what changed). `since`: a history step number, {"mine": N} (before your own last N steps: check what your edits really did), {"steps": N} or {"version": "name"}; `until`: a later step (default now). Narrow with `track`, `section` or `from` / `to`. Notes are matched by id, so a note moved to another track shows as removed there and added here. Read-only."""
        doc = ctx.document(args.get("item"))
        seq, said = since_step(doc, args["since"], ctx.who)
        until = args.get("until", doc.seq)
        if not seq <= until <= doc.seq:
            raise RostrumError(codes.BAD_ARGUMENT, "inspect_note_changes", f"until {until}",
                               f"must be from step {seq} to {doc.seq}")
        before, after = state_at(doc, seq), state_at(doc, until)
        tracks = None
        if args.get("track"):
            known = {t["id"] for s in (before, after) for t in s.get("tracks", [])}
            if args["track"] not in known:
                raise RostrumError.not_found("inspect_note_changes", "track", args["track"], sorted(known))
            tracks = {args["track"]}
        window = _bounds(after, args) if any(k in args for k in ("section", "from", "to")) else None
        diff = ND.changes(before, after, tracks, window)
        n = ND.counts(diff)
        head = (f"{said} → {'now, ' if until == doc.seq else ''}step {until}: "
                f"{n['added']} added, {n['removed']} removed, {n['changed']} changed.")
        if not diff:
            head += " No note or drum hit differs."
        data = {"since": seq, "until": until, **n,
                "tracks": {t: {k: [r[0] for r in v] for k, v in d.items()} for t, d in diff.items()}}
        return Reply("\n".join([head] + words(diff, before, after, args.get("limit", LIMIT))), data)
