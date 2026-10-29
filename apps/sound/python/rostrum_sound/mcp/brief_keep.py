"""A kept fault must be one the brief asks for, quoted from it: the shared screen (rostrum_core.mcp.brief_keep), with
Sound's word tables (../brief.py: which words mean the brief asks for a dull top, a held tone, ...) registered into it.
Runs after asked_keep.screen (the moment the brief asked for has its own, stricter rule)."""
from __future__ import annotations

from rostrum_core.mcp.brief_keep import NO_BRIEF, kind, screen, why_not  # noqa: F401  (Sound's callers read them here)

from .. import brief  # noqa: F401  (registers Sound's per-kind words before any screen runs)
