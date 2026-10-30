"""Markup-native 2D (2026-10-30): an agent writes a film as HTML + inline SVG + CSS from Python, and Rostrum keys any
attribute or CSS value, moves a camera, lights shapes, adds grain, blurs motion and syncs mouths on top. It is the 2D
agent surface (`python -m rostrum2d.mcp`, tools in markup/mcp.py); nothing in the document path uses it."""
from .film import Film, Mouth
from .values import Keys, clamp, keys, lerp, mix, spring, wave

__all__ = ["Film", "Mouth", "Keys", "keys", "lerp", "clamp", "mix", "spring", "wave"]
