"""The one reply shape (shared/mcp/CONVENTIONS.md § 4) and the one error reply (§ 6)."""
from __future__ import annotations

from dataclasses import dataclass, field

from ..errors import RostrumError
from .faults import lines


@dataclass
class Reply:
    """What a tool returns. `images` are PNG bytes or an absolute path to a PNG; they also go out as MCP images."""
    summary: str
    data: dict = field(default_factory=dict)
    files: list = field(default_factory=list)
    images: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    changed: dict | None = None      # edits only: {"seq": 7, "ops": ["layer.move"], "group": "...", "new_check_failures": []}
    faults: list | None = None       # notes the agent asked for (`notes: true`): [] = checked, nothing noted (faults.py)

    def to_dict(self) -> dict:
        out = {"ok": True, "summary": self.summary, "data": self.data,
               "files": [str(f) for f in self.files], "warnings": list(self.warnings)}
        if self.faults is not None:      # asked-for notes close the summary: observations, never a verdict on the work
            out["summary"] = f"{self.summary}\n{lines(self.faults)}"
            out["notes"] = list(self.faults)
        if self.changed is not None:
            out["changed"] = self.changed
        return out


def error_dict(err: RostrumError) -> dict:
    """ok:false, the one line, and the error object. Never a second format."""
    return {"ok": False, "summary": err.line(), "error": err.to_dict()}
