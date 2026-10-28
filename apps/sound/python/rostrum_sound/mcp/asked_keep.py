"""The moment the brief asked for is harder to keep than any other fault.

Round deliver-clean: with `keep` one sentence away, agents shipped in 7 of 10 runs with a fault on the very moment the
brief asked for (a weak hit, a soft stop, a weak climax), often on the first render that named it. So a fault at an
asked moment (`expect`, or a marker named hit / stop / drums out / climax …) says so in its own words ("the moment
the brief asked for"), and `keep` lets it through only when (1) the previous render named it too, so one fix was
tried, and (2) the reason quotes a measured number (what was measured, not "on purpose"). Otherwise the keep entry
is set aside and the fault's fix says why; the shared gate (rostrum_core.mcp.faults.deliver) then refuses as usual.
Every other fault keeps the shared rule: any reason."""
from __future__ import annotations

import re

NEAR_S = 0.1           # a fault this close to an asked moment's time is on it
WHOLE = ("held_tone", "near_mono", "dull_top", "leading_silence", "off_tempo")


def mark(raw: list[dict], shaped: list[dict], moments) -> None:
    """Tag the shaped faults (one per raw fault, same order: fault_shape.shape) that sit on an asked moment."""
    times = [(float(m["at"]), m.get("kind", "hit")) for m in moments or [] if m.get("at") is not None]
    for r, f in zip(raw, shaped):
        if r["kind"] in WHOLE:
            continue
        hit = next((k for t, k in times if abs(t - float(r.get("at_s") or 0.0)) <= NEAR_S), None)
        if hit:
            f["asked"] = True
            f["what"] = f"the moment the brief asked for ({hit} at {float(r['at_s']):.2f} s): {f['what']}"


def screen(found: list[dict], keep: dict | None, seen_before: set) -> dict:
    """`keep` without the entries an asked-moment fault may not use yet; each refused one says why in its fault's fix."""
    keep = dict(keep or {})
    for f in found:
        why = keep.get(f["id"])
        if not f.get("asked") or why is None:
            continue
        missing = []
        if f["id"] not in seen_before:
            missing.append("the previous render did not name it, so no fix was tried yet: render once more after a fix")
        if not re.search(r"\d", why):
            missing.append("the reason must quote what you measured (a number from the check)")
        if missing:
            del keep[f["id"]]
            f["fix"] = f"{f['fix']} (keep refused for the brief's own moment: {'; '.join(missing)})"
    return keep
