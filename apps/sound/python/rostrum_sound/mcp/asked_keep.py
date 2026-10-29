"""The moment the brief asked for is harder to keep than any other fault.

Round deliver-clean: with `keep` one sentence away, agents shipped in 7 of 10 runs with a fault on the very moment the
brief asked for. Round 3E tightened that to "a fix was tried and the reason quotes a number", and three judge faults
were still moments kept that way (a hit 0.9x a normal note, a stop +0.18 LU, drums back weakly). So now a fault at an
asked moment (`expect`, or a marker named hit / stop / drums out / climax …) says so in its own words ("the moment the
brief asked for") and always shows what a passing version measures (listen/passing.py), and `keep` lets it through
only when (1) the previous render named it too, so one fix was tried, and (2) the moment measures within the stated
distance of passing. Further off, the moment is fixed, or moved on purpose (moment(name, at=...) / `expect` in the
script: the check then reads the new time). A refused keep entry is set aside and the fault's fix says why; the shared
gate (rostrum_core.mcp.faults.deliver) then refuses as usual. Every keep, this one too, must also quote the brief that
asks for it (brief_keep.py, run after this screen)."""
from __future__ import annotations

from ..listen import passing

NEAR_S = 0.1           # a fault this close to an asked moment's time is on it
WHOLE = ("held_tone", "near_mono", "dull_top", "leading_silence", "off_tempo", "dead_air_end")
MOVE = ("or, if the brief allows another time, move the moment itself in the script (moment(name, at=...) or `expect`) "
        "so the check reads it there")


def mark(raw: list[dict], shaped: list[dict], moments) -> dict:
    """Tag the shaped faults (one per raw fault, same order: fault_shape.shape) that sit on an asked moment, add what
    a passing version measures to their `what`, and return {fault id: near passing} for screen()."""
    times = [(float(m["at"]), m.get("kind", "hit")) for m in moments or [] if m.get("at") is not None]
    near = {}
    for r, f in zip(raw, shaped):
        if r["kind"] in WHOLE:
            continue
        hit = next((k for t, k in times if abs(t - float(r.get("at_s") or 0.0)) <= NEAR_S), None)
        if hit:
            f["asked"] = True
            bar = passing.words(r)
            f["what"] = f"the moment the brief asked for ({hit} at {float(r['at_s']):.2f} s): {f['what']}" + (f"; {bar}" if bar else "")
            near[f["id"]] = passing.near(r)
    return near


def screen(found: list[dict], keep: dict | None, seen_before: set, near: dict | None = None) -> dict:
    """`keep` without the entries an asked-moment fault may not use; each refused one says why in its fault's fix.
    `near`: mark()'s {id: within the stated distance of passing} (an asked fault missing from it is not near)."""
    keep, near = dict(keep or {}), near or {}
    for f in found:
        if not f.get("asked") or f["id"] not in keep:
            continue
        missing = []
        if f["id"] not in seen_before:
            missing.append("the previous render did not name it, so no fix was tried yet: render once more after a fix")
        if not near.get(f["id"]):
            missing.append("it measures too far from passing (its what says what passes and from where it may be kept): "
                           f"fix it {MOVE}")
        if missing:
            del keep[f["id"]]
            f["fix"] = f"{f['fix']} (keep refused for the brief's own moment: {'; '.join(missing)})"
    return keep
