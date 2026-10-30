"""Markup-native 2D (proof, 2026-10-30): an agent writes a film as HTML + inline SVG + CSS from Python, and Rostrum
keys any attribute or CSS value, moves a camera, lights shapes, blurs motion and syncs mouths on top. Design:
C:/Users/Sam/.rostrum/waves/results/2d-markup-design/DESIGN.md. Reached only through its own MCP server
(python -m rostrum2d.markup.mcp); nothing in the document path uses it."""
from .film import Film, Mouth
from .values import Keys, clamp, keys, lerp, mix, spring, wave

__all__ = ["Film", "Mouth", "Keys", "keys", "lerp", "clamp", "mix", "spring", "wave"]
