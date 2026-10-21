"""Cleanup of recorded audio (PLAN › RostrumSound › Cleanup; rule 7: computed once, stored by content).

A clip keeps its original `media`; its cleanup settings (`isolate`, `denoise`, `dereverb`, `stem`) describe a cleaned
take that is made once on request into the shared cache and played instead while `useCleaned` is on. Each step is
its own cache entry keyed by its input's content, the model and its version and the step's settings, so changing
one setting redoes only the steps after it. The models are the vetted list in `models.py` (apps/sound/MODELS.md),
loaded for the job and released after it.

    r = cleanup.make("take.wav", {"denoise": 0.8, "dereverb": 0.5})   # -> Result(file, generated, steps)
    cleanup.cached("take.wav", {"denoise": 0.8, "dereverb": 0.5})       # the file, or None (never runs a model)
    cleanup.make("song.wav", {"stem": "drums"})                          # one stem (all four are made together)

Order of steps: stem / isolate (separation) -> denoise -> dereverb.
"""
from __future__ import annotations

from .chain import STEMS, Result, cached, make, needs_cleanup, recipe_of

__all__ = ["STEMS", "Result", "cached", "make", "needs_cleanup", "recipe_of"]
