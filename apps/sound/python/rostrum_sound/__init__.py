"""RostrumSound's Python layer: the Sound document (items and operations on rostrum_core), its script layer,
and the compiler to the engine's schedule (`rostrum-sound-schedule/1`)."""
from .compile import compile
from .doc import KIND, REGISTRY
from .script import run_source

__all__ = ["KIND", "REGISTRY", "compile", "run_source"]
