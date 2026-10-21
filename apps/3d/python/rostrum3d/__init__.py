"""Rostrum3D's Python layer: the 3D document and its operations on rostrum_core, the script layer, the compiler
that turns one shot into the scene description the C++ core builds its USD stage from (../ENGINE_CONTRACT.md),
the engine client and the agent tools."""
from .kind import KIND, REGISTRY
from .script import run_source

__all__ = ["KIND", "REGISTRY", "run_source"]
