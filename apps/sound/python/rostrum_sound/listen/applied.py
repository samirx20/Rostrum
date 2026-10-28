"""applied: what the last change did to a fault that is still there, measured, not assumed.

Canary 3E r8: Haiku applied dull_top's shelf, the fault came back, and nothing said the change had moved the top end
from -33.8 only to -29.1 dB against a pass line of -20, so it kept the fault instead of fixing the parts. Each render
now records its faults' measured numbers by fault id (`record`, kept with the render beside faultIds); when the next
render names the same fault, `tell` adds to its `what` what the change did: was, now, what passes, "not enough" or
"no change". The numbers and pass lines are passing.py's (each check's own); a fault without one compares its plain
measured numbers."""
from __future__ import annotations

from . import passing


def _numbers(raw: dict) -> dict:
    """{key: (now, passes, op, words, unit)} of a raw fault: its passing.py rules, else its plain numbers."""
    g = passing.gaps(raw)
    if g:
        keys = [r[0] for r in passing._rules(raw)]
        return {k: (x["now"], x["passes"], x["op"], x["what"], x["unit"]) for k, x in zip(keys, g)}
    d = raw.get("measured") or {}
    return {k: (float(v), None, None, k.replace("_", " "), "") for k, v in d.items()
            if isinstance(v, (int, float)) and not isinstance(v, bool)}


def record(raw: list[dict], shaped: list[dict]) -> dict:
    """{fault id: {key: number}} for the shaped faults that come from a raw one (same order: fault_shape.shape)."""
    return {f["id"]: {k: v[0] for k, v in _numbers(r).items()} for r, f in zip(raw, shaped)}


def _n(v: float, unit: str) -> str:
    return f"{round(v, 2):g}{'x' if unit.startswith('x') else unit}"


def tell(raw: list[dict], shaped: list[dict], before: dict | None) -> None:
    """Add to each shaped fault the previous render also named (`before`: that render's record()) what the change
    did to its numbers."""
    for r, f in zip(raw, shaped):
        was = (before or {}).get(f["id"])
        if not was:
            continue
        bits, moved, worse = [], False, False
        for k, (now, passes, op, what, unit) in _numbers(r).items():
            if k not in was or was[k] is None:
                continue
            moved = moved or abs(now - float(was[k])) >= 0.05
            worse = worse or (op is not None and (now - float(was[k])) * (1 if op == ">=" else -1) <= -0.05)
            bar = f", passes at {_n(passes, unit)} or {'more' if op == '>=' else 'less'}" if passes is not None else ""
            bits.append(f"{what} was {_n(float(was[k]), unit)}, now {_n(now, unit)}{bar}")
        if bits:
            verdict = ("it moved the wrong way: undo it and try another of the fixes" if worse else
                       "not enough: try a bigger change or another of the fixes" if moved else "no change: that change did not reach it")
            f["what"] = f"{f['what']} (after the last change: {'; '.join(bits)}: {verdict})"
