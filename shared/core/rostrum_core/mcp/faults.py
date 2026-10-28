"""Faults first (shared/mcp/CONVENTIONS.md § 4): a reply that checked the work opens with what is wrong, before anything else.

Weak agents shipped work their own check had named (a duck you can't hear, a sphere cut by the frame, a black frame):
a warning after a success line is easy to skip. So a checked reply (`Reply.faults` set, even to []) starts with

    NOT DONE: 2 faults. [loudness] -16.9 LUFS, the target is -14 (whole song); fix: ... | [cut_edge:ball] ...
    DONE: checked, no faults.

and delivery (a render to a final file) refuses open faults unless the call explains each one: `keep: {fault_id: "why"}`.
A fault is {id, what, when, fix}: `id` is stable across re-runs (the same problem keeps its id, so a `keep` still names it).
"""
from __future__ import annotations

from pathlib import Path

from ..errors import RostrumError, codes

KEEP = {"keep": {"type": "object", "additionalProperties": {"type": "string", "minLength": 3},
                 "description": "Faults you leave on purpose, each explained: {fault_id: \"why\"}, ids as the reply's faults "
                                "name them. A final file is refused while a fault is open (not fixed, not kept)."}}


def fault(id: str, what: str, fix: str, when: str | None = None) -> dict:
    """One fault: `id` stable across re-runs, `what` measured in plain words, `when` a time or marker (None: the whole
    piece / picture), `fix` what to change."""
    return {"id": id, "what": what, "when": when, "fix": fix}


def apply_keep(faults: list[dict], keep: dict | None) -> list[str]:
    """Mark the faults `keep` explains (f["kept"] = why). Returns notes for keep ids that name no fault here."""
    keep = keep or {}
    ids = {f["id"] for f in faults}
    for f in faults:
        if f["id"] in keep:
            f["kept"] = keep[f["id"]]
    return [f'keep names "{k}", which is not a fault here (faults: {", ".join(sorted(ids)) or "none"}).' for k in keep if k not in ids]


def still_open(faults: list[dict]) -> list[dict]:
    return [f for f in faults if not f.get("kept")]


def _line(f: dict) -> str:
    when = f" ({f['when']})" if f.get("when") else ""
    return f"[{f['id']}] {f['what']}{when}; fix: {f['fix']}"


def headline(faults: list[dict]) -> str:
    """The reply's first line: NOT DONE with every open fault (what, when, fix), or DONE (with what was kept)."""
    left, kept = still_open(faults), [f for f in faults if f.get("kept")]
    said = f" Kept on purpose: {', '.join(f['id'] for f in kept)}." if kept else ""
    if not left:
        return f"DONE: checked, no open faults.{said}"
    return f"NOT DONE: {len(left)} fault{'s' * (len(left) != 1)}. " + " | ".join(_line(f) for f in left) + said


def deliver(faults: list[dict], keep: dict | None, where: str, file: str | Path | None = None) -> list[str]:
    """The gate before a final file counts as delivered. Open faults: the file (if written) is renamed
    `<name>.NOT-DONE<ext>` so nothing ships under the asked-for name, and the call fails naming each fault and the
    `keep` that would let it through. Returns apply_keep's notes when everything is fixed or explained."""
    notes = apply_keep(faults, keep)
    left = still_open(faults)
    if not left:
        return notes
    moved = ""
    if file is not None and Path(file).is_file():
        p = Path(file)
        held = p.with_name(f"{p.stem}.NOT-DONE{p.suffix}")
        held.unlink(missing_ok=True)
        p.replace(held)
        moved = f" The file was kept for listening/looking as {held}, not delivered."
    example = ", ".join(f'"{f["id"]}": "why it stays"' for f in left[:3])
    raise RostrumError(codes.CHECK_FAILED, where, "the delivery", headline(faults) + moved,
                       [f["id"] for f in left],
                       f"Fix each fault and render again, or explain the ones you keep on purpose: keep {{{example}}}.")
