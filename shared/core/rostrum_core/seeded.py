"""The random numbers a script may use: always the same ones for the same seed, so running a script again gives the same
piece and a person's edits stay matched to it.

    random.uniform(0, 1)          # the script's own generator, seeded 1 at the start of every run
    r = random(7)                 # another generator with its own seed: r.random(), r.uniform(a, b), r.randint(a, b), r.choice(seq)
    random.seed(3)                # reseed the script's own generator
    random.Random(7)              # Python's own class, as in any program
"""
from __future__ import annotations

import random as _random


class SeededRandom(_random.Random):
    """A generator seeded 1; called with a seed it gives a new one (`random(7)`), so a loop can seed per item. It stands
    in for the `random` module, so the module's classes are on it too (`random.Random(7)`, `from random import Random`)."""
    Random = _random.Random
    SystemRandom = _random.SystemRandom

    def __init__(self, seed: int = 1):
        super().__init__(seed)

    def __call__(self, seed: int = 1) -> _random.Random:
        return _random.Random(seed)

