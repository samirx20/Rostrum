"""Safe expressions for one field: a small tokenizer and recursive-descent parser over a FIXED list of functions.
Nothing here uses Python's eval / compile / ast, so an expression can only do what this file lets it do.

    expr   := or ['if' or 'else' expr]                    a if c else b   (c is true when not 0)
    or     := and ('or' and)*      and := not ('and' not)*      not := 'not' not | cmp
    cmp    := sum [('<' '<=' '>' '>=' '==' '!=') sum]     gives 1 or 0 (one comparison, no chains)
    sum    := term (('+' | '-') term)*       term := unary (('*' | '/' | '%') unary)*
    unary  := ('-' | '+') unary | power      power := atom [('^' | '**') unary]      (-2^2 = -4, 2^-1 = 0.5)
    atom   := number | #rrggbb | name | name(args) | ref("item.field"[, time]) | marker("name") | (expr)

Names: time (s), frame, fps, duration, pi, e, true, false, and `item.field` (a dotted name = that item's field at
the same time; `ref("a-b.x", time - 0.2)` is the same with a quoted id and a shifted time). Functions: sin cos
(radians) abs sqrt floor ceil round(x + 0.5 rounded down) min max clamp(x, lo, hi) lerp(a, b, p) (numbers or
colours) noise(x[, seed]) pulse([decay]) (1 on each beat of the project's sound, falling straight to 0 over
decay seconds, default 0.25; the beat grid is RostrumSound's). Colours are #rrggbb. `noise` is value noise in -1..1, the same on every machine: with
h(n) = hash of the whole number n and the seed, i = floor(x), f = x - i, u = f·f·(3 - 2f), the result is
h(i) + (h(i+1) - h(i))·u; the hash is 32-bit integer arithmetic only (see `_hash`).
"""
from __future__ import annotations

import re

from rostrum_core.errors import did_you_mean

from .expr_lib import CMPS, CONSTS, FUNCS, STATIC, VARS, ExprError  # noqa: F401  (ExprError is re-exported)

TOKEN = re.compile(r"""\s*(?:(?P<num>\d+\.?\d*(?:[eE][+-]?\d+)?|\.\d+)
                       |(?P<name>[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)
                       |(?P<str>"[^"]*"|'[^']*')
                       |(?P<col>\#[0-9A-Fa-f]{6}\b)
                       |(?P<op>\*\*|<=|>=|==|!=|[-+*/%^()<>,]))""", re.X)
WORDS = {"if", "else", "and", "or", "not"}

def tokens(src: str) -> list[tuple]:
    out, pos = [], 0
    while True:
        m = TOKEN.match(src, pos)
        if m is None:
            rest = src[pos:]
            if rest.strip():
                raise ExprError(f'unexpected "{rest.strip()[0]}"', pos + len(rest) - len(rest.lstrip()) + 1)
            return out + [("end", "", len(src) + 1)]
        kind = m.lastgroup
        text = m.group(kind)
        out.append(("op" if kind == "name" and text in WORDS else kind, text, m.start(kind) + 1))
        pos = m.end()


class Parser:
    def __init__(self, src: str):
        self.toks, self.i = tokens(src), 0

    def peek(self):
        return self.toks[self.i]

    def take(self):
        self.i += 1
        return self.toks[self.i - 1]

    def want(self, text: str):
        kind, t, col = self.take()
        if t != text or kind not in ("op", "end"):
            raise ExprError(f'expected "{text}" but found {self._what(kind, t)}', col)

    @staticmethod
    def _what(kind, t):
        return "the end" if kind == "end" else f'"{t}"'

    def parse(self):
        node = self.expr()
        kind, t, col = self.peek()
        if kind != "end":
            raise ExprError(f"unexpected {self._what(kind, t)} after a complete expression", col)
        return node

    def expr(self):
        a = self.or_()
        if self.peek()[1] == "if" and self.peek()[0] == "op":
            col = self.take()[2]
            c = self.or_()
            self.want("else")
            return ("if", col, c, a, self.expr())
        return a

    def _chain(self, ops, sub, kind="bin"):
        a = sub()
        while self.peek()[0] == "op" and self.peek()[1] in ops:
            _, op, col = self.take()
            a = (kind, col, op, a, sub())
        return a

    def or_(self):
        return self._chain(("or",), self.and_, "logic")

    def and_(self):
        return self._chain(("and",), self.not_, "logic")

    def not_(self):
        if self.peek()[:2] == ("op", "not"):
            return ("not", self.take()[2], self.not_())
        a = self.sum()
        if self.peek()[0] == "op" and self.peek()[1] in CMPS:
            _, op, col = self.take()
            return ("cmp", col, op, a, self.sum())
        return a

    def sum(self):
        return self._chain(("+", "-"), self.term)

    def term(self):
        return self._chain(("*", "/", "%"), self.unary)

    def unary(self):
        if self.peek()[0] == "op" and self.peek()[1] in ("-", "+"):
            _, op, col = self.take()
            inner = self.unary()
            return ("neg", col, inner) if op == "-" else inner
        base = self.atom()
        if self.peek()[0] == "op" and self.peek()[1] in ("^", "**"):
            col = self.take()[2]
            return ("bin", col, "^", base, self.unary())
        return base

    def atom(self):
        kind, t, col = self.take()
        if kind == "num":
            return ("num", col, float(t))
        if kind == "col":
            return ("num", col, t.lower())
        if kind == "op" and t == "(":
            node = self.expr()
            self.want(")")
            return node
        if kind != "name":
            raise ExprError(f"expected a value but found {self._what(kind, t)}", col)
        if self.peek()[:2] == ("op", "("):
            return self.call(t, col)
        if "." in t:
            item, prop = t.rsplit(".", 1)
            return ("ref", col, item, prop, None)
        if t in VARS or t in CONSTS:
            return ("var", col, t)
        if t in FUNCS or t in STATIC:
            raise ExprError(f'"{t}" is a function: write {t}(…)', col)
        raise ExprError(f'unknown name "{t}"; names: {", ".join([*VARS, *CONSTS])}, or item.field ({t}.x)', col)

    def call(self, name: str, col: int):
        self.take()                                              # (
        if name in STATIC:
            kind, t, scol = self.take()
            if kind != "str":
                raise ExprError(f'{name}( needs a quoted name first: {name}("logo.x")', scol)
            args = [t[1:-1]]
            if self.peek()[1] == "," and name == "ref":
                self.take()
                args.append(self.expr())
            self.want(")")
            if name == "marker":
                return ("marker", col, args[0])
            if "." not in args[0]:
                raise ExprError(f'ref("{args[0]}"): write item.field, e.g. ref("logo.x")', scol)
            item, prop = args[0].rsplit(".", 1)
            return ("ref", col, item, prop, args[1] if len(args) > 1 else None)
        if name not in FUNCS:
            raise ExprError(f'unknown function "{name}"; functions: {", ".join([*FUNCS, *STATIC])}'
                            + (f" {did_you_mean(name, [*FUNCS, *STATIC])}" if did_you_mean(name, [*FUNCS, *STATIC]) else ""), col)
        args = []
        if self.peek()[:2] != ("op", ")"):
            args.append(self.expr())
            while self.peek()[:2] == ("op", ","):
                self.take()
                args.append(self.expr())
        self.want(")")
        lo, hi, _ = FUNCS[name]
        if not lo <= len(args) <= hi:
            raise ExprError(f"{name}() takes {lo if lo == hi else f'{lo} to {hi}'} values, not {len(args)}", col)
        return ("call", col, name, args)


def parse(source: str):
    """Source text -> tree (tuples). Raises ExprError with the column of the problem."""
    if not isinstance(source, str) or not source.strip():
        raise ExprError("the expression is empty", 1)
    return Parser(source).parse()


def find(node, kind: str):
    """Every node of that kind in the tree (known without running it: loops and markers are found from this)."""
    if node[0] == kind:
        yield node
    for part in node[2:]:
        for p in part if isinstance(part, list) else [part]:
            if isinstance(p, tuple):
                yield from find(p, kind)


def refs(node) -> dict[tuple[str, str], int]:
    """Every (item id, field) the expression reads, with the column of its first mention."""
    return {(n[2], n[3]): n[1] for n in reversed(list(find(node, "ref")))}

