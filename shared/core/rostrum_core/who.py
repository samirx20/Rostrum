"""Who made a change: a person (GUI), an agent (MCP, named by its client), a script (by file), or outside.

Filled in by rostrum_core's callers at the door (GUI bridge, MCP server, script runner), never by an operation.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePath

KINDS = ("person", "agent", "script", "outside")
_AGENTS = (("claude", "Claude"), ("codex", "Codex"), ("gemini", "Gemini"), ("cursor", "Cursor"))


@dataclass(frozen=True)
class Who:
    kind: str
    name: str

    def __post_init__(self):
        if self.kind not in KINDS:
            raise ValueError(f"who.kind must be one of {KINDS}, not {self.kind!r}")

    @classmethod
    def person(cls, name="you"): return cls("person", name)
    @classmethod
    def agent(cls, name): return cls("agent", name)
    @classmethod
    def script(cls, name): return cls("script", name)
    @classmethod
    def outside(cls, name="outside"): return cls("outside", name)

    def to_dict(self) -> dict:
        return {"kind": self.kind, "name": self.name}

    @classmethod
    def from_dict(cls, d) -> "Who":
        return cls(d["kind"], d["name"])

    def words(self) -> str:
        """Who in plain words, the one place a Who becomes a name on screen or in a refusal: a person by name ("Sam"),
        an agent by its app ("claude-code" -> "Claude"), a script by its file name, "Outside Rostrum"."""
        if self.kind == "agent":
            low = self.name.lower()
            return next((w for k, w in _AGENTS if low.startswith(k)), self.name[:1].upper() + self.name[1:])
        if self.kind == "script":
            return PurePath(self.name.replace("\\", "/")).name or self.name
        if self.kind == "outside":
            return "Outside Rostrum"
        return self.name[:1].upper() + self.name[1:]

    def __str__(self):
        return f"{self.kind}:{self.name}"


UPGRADE = Who("outside", "Rostrum (older file)")   # an older file brought up to date on open: nobody's edit
