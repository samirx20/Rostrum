"""Where 03_walls.py put its windows: the same seed and the same draws, without painting.

Used by later scripts to put reflections and glows exactly on the lit windows.
"""
import random


class _Nop:
    def batch(self, *a, **k):
        import contextlib
        return contextlib.nullcontext()

    def __getattr__(self, name):
        return lambda *a, **k: 0


def lit_windows():
    import importlib.util, os
    spec = importlib.util.spec_from_file_location("_w03", os.path.join(os.path.dirname(__file__), "03_walls.py"))
    mod = importlib.util.module_from_spec(spec)
    mod.doc = _Nop()
    spec.loader.exec_module(mod)  # replays 03's random draws with a do-nothing doc
    return mod.lit_r, mod.lit_l
