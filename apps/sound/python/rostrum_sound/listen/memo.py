"""One memory of finished analyses, so a second look at the same render costs nothing.

A look reads a rendered file and measures it; the answer cannot change until the file does. `remembered` wraps an
analysis function: the key is the function plus every argument, where a path to a file counts as that file's path,
size and modified time (a new render is a new file state, so it measures again). Lives for the server's run, holds
the newest MAX answers (small dicts and arrays, not audio), and hands each caller its own copy to edit."""
from __future__ import annotations

import copy
import functools
import inspect
import os
from collections import OrderedDict

MAX = 64
_store: OrderedDict = OrderedDict()


def _stamp(x):
    """Hashable stand-in for an argument: files by path + size + mtime, containers by their parts, the rest as written."""
    if isinstance(x, (str, os.PathLike)):
        p = os.fspath(x)
        try:
            if os.path.isfile(p):
                s = os.stat(p)
                return ("file", p, s.st_size, s.st_mtime_ns)
        except OSError:
            pass
        return p
    if isinstance(x, dict):
        return tuple((k, _stamp(v)) for k, v in x.items())
    if isinstance(x, (list, tuple, set)):
        return tuple(_stamp(v) for v in x)
    if hasattr(x, "shape"):                  # loaded audio: nothing to key it by
        raise TypeError("not keyable")
    return repr(x)


def remembered(fn):
    sig = inspect.signature(fn)

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            given = sig.bind(*args, **kwargs).arguments        # a path the function writes (out_png) is a name, not an input
            key = (fn.__module__, fn.__qualname__, tuple(
                (k, os.fspath(v) if k.startswith("out") and isinstance(v, (str, os.PathLike)) else _stamp(v)) for k, v in given.items()))
        except TypeError:
            return fn(*args, **kwargs)
        hit = _store.get(key)
        if hit is not None and not (isinstance(hit, dict) and hit.get("png") and not os.path.isfile(hit["png"])):
            _store.move_to_end(key)
            return copy.deepcopy(hit)
        out = fn(*args, **kwargs)
        _store[key] = copy.deepcopy(out)
        while len(_store) > MAX:
            _store.popitem(last=False)
        return out
    return wrapper
