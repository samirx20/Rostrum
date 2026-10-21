"""Rostrum2D's Python layer: the 2D document and its operations on rostrum_core, the script layer, the scene
description the Rust engine evaluates per frame (../ENGINE_CONTRACT.md), and the agent tools."""
from .kind import KIND, REGISTRY
from .script import run_source

__all__ = ["KIND", "REGISTRY", "run_source"]
