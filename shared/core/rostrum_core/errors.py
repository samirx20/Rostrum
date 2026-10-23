"""The one error type and its plain one-line message (shared/mcp/CONVENTIONS.md § 6).

Every failure in Rostrum, from an operation, a script, a job or an MCP tool, is a RostrumError with one of
the codes below. The GUI, CLI and MCP all show `error.line()`; nothing invents a second format.
"""
from __future__ import annotations

import difflib
import re
from types import SimpleNamespace

codes = SimpleNamespace(**{c: c for c in (
    "UNKNOWN_TOOL", "UNKNOWN_OPERATION", "BAD_ARGUMENT", "NOT_FOUND", "CONFLICT", "CHECK_FAILED",
    "RENDER_FAILED", "JOB_FAILED", "JOB_INTERRUPTED", "MODEL_MISSING", "NO_MEMORY", "INTERNAL")})
ALL_CODES = frozenset(vars(codes))


def did_you_mean(word, choices) -> str | None:
    close = difflib.get_close_matches(str(word), [str(c) for c in choices], n=1, cutoff=0.6)
    return f"Did you mean {close[0]}?" if close else None


class RostrumError(Exception):
    """code, where (which call / op), subject (what was given), problem, accepted (what would work), hint."""

    def __init__(self, code: str, where: str, subject: str, problem: str, accepted=(), hint: str | None = None,
                 plain: str | None = None):
        if code not in ALL_CODES:
            raise ValueError(f"unknown error code {code!r}")
        self.code, self.where, self.subject, self.problem = code, where, subject, problem
        self.accepted = [str(a) for a in accepted]
        self.hint = hint
        self.plain = plain                  # the sentence for a person, when the operation knows one (see person())
        super().__init__(self.line())

    def line(self) -> str:
        text = f"Error: {self.where}: {self.subject} {self.problem}."
        if self.accepted:
            shown = ", ".join(self.accepted[:12]) + (", …" if len(self.accepted) > 12 else "")
            text += f" Accepted: {shown}."
        if self.hint:
            text += f" {self.hint}"
        return text

    def person(self) -> str:
        """The one place an error becomes a person's message (the screens show this; agents and the console get line()).
        An operation says it in its own words with `plain`; any other error is cleaned: no "Error: op 1 of 1 (paint.fill):"
        prefix, no ids in brackets, long decimals rounded."""
        if self.plain:
            return self.plain
        text = f"{self.subject} {self.problem}.".strip()
        text = re.sub(r"\s*\([a-z0-9_.\-]+\)", "", text)                             # (layer_id)
        text = re.sub(r"\d+\.\d{3,}", lambda m: f"{float(m.group()):.0f}", text)        # 959.7945 -> 960
        return (text + (f" {self.hint}" if self.hint else "")).strip()

    def to_dict(self) -> dict:
        return {"code": self.code, "where": self.where, "subject": self.subject, "problem": self.problem,
                "accepted": self.accepted, "hint": self.hint}

    def within(self, prefix: str) -> "RostrumError":
        where = f"{prefix} › {self.where}" if self.where else prefix
        return RostrumError(self.code, where, self.subject, self.problem, self.accepted, self.hint, self.plain)

    @classmethod
    def not_found(cls, where: str, what: str, word, choices, in_: str = "this document") -> "RostrumError":
        return cls(codes.NOT_FOUND, where, f'"{word}"', f"no {what} \"{word}\" in {in_}",
                   sorted(choices), did_you_mean(word, choices))
