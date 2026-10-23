"""Spatial handles: a number key's optional `out` (the handle leaving it) and `in` (the handle arriving at it), offsets
in the field's own units (px for x / y), bend the way between two keys into a cubic Bézier. The one formula, read
by the evaluator (evaluate.py) and by `after.py`'s carry-on speed; the Rust engine's `between` is the same.
"""
from __future__ import annotations


def between(k0: dict, k1: dict, p: float) -> float:
    """A number field between two keys at eased progress p. Without spatial handles (k0's `out`, k1's `in`) it is
    the straight a + (b − a)·p; with either, the cubic Bézier a, a + out, b + in, b (a missing handle is a third of
    the way along the straight line) at parameter p. x and y each do this with their own ease, so x and y keys with
    the same ease travel a true 2D Bézier path. Speed along the curve follows p, not the arc length (a known
    simplification). The engine's `between` is the same (ENGINE_CONTRACT.md › Evaluation)."""
    a, b = k0["v"], k1["v"]
    if "out" not in k0 and "in" not in k1:
        return a + (b - a) * p
    c1 = a + k0.get("out", (b - a) / 3)
    c2 = b + k1.get("in", -(b - a) / 3)
    q = 1 - p
    return q * q * q * a + 3 * q * q * p * c1 + 3 * q * p * p * c2 + p * p * p * b
