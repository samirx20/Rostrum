"""Running a parsed expression (expr.py): a float, or a "#rrggbb" string. No Python eval; each node kind is
handled here and nowhere else."""
from __future__ import annotations

import math

from rostrum_core.keys import mix_color
from rostrum_core.markers import lookup
from .expr_lib import CMPS, CONSTS, FUNCS, ExprError


def _num(v, col):
    if isinstance(v, str):
        raise ExprError("a colour can't be used as a number here", col)
    return v


def _truth(node, env) -> bool:
    return _num(run(node, env), node[1]) != 0


def _compare(op, a, b, col):
    if isinstance(a, str) or isinstance(b, str):
        if not (isinstance(a, str) and isinstance(b, str) and op in ("==", "!=")):
            raise ExprError("colours can only be compared with == and != to another colour", col)
    return float(CMPS[op](a, b))


def _arith(op, a, b):
    if op == "+":
        return a + b
    if op == "-":
        return a - b
    if op == "*":
        return a * b
    return a / b if op == "/" else a % b if op == "%" else a ** b


def run(node, env):
    """`env`: time, frame, fps, duration, markers ({name: seconds} | None) and get(item, field, t) -> value."""
    k, col = node[0], node[1]
    if k == "num":
        return node[2]
    if k == "var":
        return CONSTS[node[2]] if node[2] in CONSTS else getattr(env, node[2])
    if k == "ref":
        return env.get(node[2], node[3], env.time if node[4] is None else _num(run(node[4], env), col))
    if k == "marker":
        if env.markers is None:
            raise ExprError(f'marker("{node[2]}"): this document is not in a project folder, so it has no '
                            "shared markers to read", col)
        at = lookup(env.markers, node[2])
        if at is None:
            raise ExprError(f'no marker "{node[2]}" in the project; there are: {", ".join(env.markers) or "none"}', col)
        return at
    if k == "if":
        return run(node[3] if _truth(node[2], env) else node[4], env)
    if k == "not":
        return float(not _truth(node[2], env))
    if k == "neg":
        return -_num(run(node[2], env), col)
    if k == "logic":
        return float(_truth(node[3], env) and _truth(node[4], env) if node[2] == "and"
                     else _truth(node[3], env) or _truth(node[4], env))
    if k == "cmp":
        return _compare(node[2], run(node[3], env), run(node[4], env), col)
    if k == "call":
        args = [run(a, env) for a in node[3]]
        if node[2] == "lerp" and isinstance(args[0], str):
            return mix_color(args[0], _colour(args[1], col), min(1.0, max(0.0, _num(args[2], col))))
        nums = [_num(a, col) for a in args]
        do = lambda: FUNCS[node[2]][2](*nums)  # noqa: E731
    else:
        a, b = _num(run(node[3], env), col), _num(run(node[4], env), col)
        do = lambda: _arith(node[2], a, b)  # noqa: E731
    try:
        v = do()
    except ZeroDivisionError:
        raise ExprError("division by zero", col) from None
    except OverflowError:
        raise ExprError("the number is too large", col) from None
    except ValueError as e:
        raise ExprError(f"{node[2]}: {e}", col) from None
    if isinstance(v, complex) or not math.isfinite(v):
        raise ExprError("the result is not a finite number", col)
    return float(v)


def _colour(v, col):
    if not isinstance(v, str):
        raise ExprError("lerp(colour, …) needs a colour as its second value too", col)
    return v
