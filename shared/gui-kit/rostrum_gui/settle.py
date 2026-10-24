"""Waiting until a scripted window has settled, before its picture is taken (--shot) or its layout checked.

An offscreen window draws only when asked, and its animations step one frame per drawn frame: a picture taken
on a timer alone showed the state of a few frames in (a tool highlight half-way, icons still loading, a menu not
yet open). `settle` draws frame after frame, letting events (image loads, Loaders) run in between, until the
picture stays the same for `still` frames in a row; it fails loudly when that never happens within `limit` seconds
(something keeps moving). Pictures still loading (an Image or a Loader with `asynchronous`) keep it waiting too, and so
does any animation or transition still running (a list sliding in can match its picture for 4 frames mid-way and look settled).
"""
from __future__ import annotations

import time

STILL = 4          # this many frames in a row with the same picture = settled (a caret blink rarely spans it)
LIMIT = 10.0       # seconds; then it fails, naming the wait


def settle(win, then, fail, still: int = STILL, limit: float = LIMIT, ready=None) -> None:
    """Draw `win` until its picture holds still, then call then(image); fail(message) when it never does. `ready()`
    (when given) must also be true on that frame: the app's own "the newest frame has landed"."""
    from PySide6.QtCore import QTimer
    end = time.monotonic() + limit
    state = {"last": None, "same": 0}

    def frame():
        img = win.grabWindow()                 # draws one frame: animations step, finished loads show
        if img.isNull():
            return fail("settle: the window gave no picture")
        state["same"] = state["same"] + 1 if state["last"] is not None and img == state["last"] else 0
        state["last"] = img
        try:
            done = (state["same"] >= still and not loading(win.contentItem()) and not animating(win.contentItem()) and (ready is None or ready()))
        except Exception as e:  # noqa: BLE001  a check that breaks must say so, never hang the run
            return fail(f"settle: {e}")
        if done:
            return then(img)
        if time.monotonic() > end:
            return fail(f"settle: the screen was still changing after {limit:g} s (an endless animation, or "
                        "something that keeps loading); no picture taken")
        QTimer.singleShot(10, frame)           # events in between: image loads, Loaders, queued signals

    frame()


def grab_settled(win, ready=None, still: int = 3, limit: float = 10.0, may_move: bool = False):
    """The one mid-run `snap`: the window's picture once what the last step changed has been drawn. A bare
    `win.grabWindow()` draws one frame of the state it finds: queued signals not yet delivered, a picture still
    on its way from a worker, a reveal or Behavior at its first frame all show the screen one change late, even
    after a `wait`. This blocks (events run in between) until `ready()` (the app's "newest picture has landed") is
    true and the picture has held for `still` frames, nothing loading or animating. Fails loudly when it never
    does; `may_move` (a progressive render refining forever) returns the last frame instead."""
    import time as _t
    from PySide6.QtCore import QCoreApplication
    end, last, same = _t.monotonic() + limit, None, 0
    while True:
        QCoreApplication.processEvents()
        img = win.grabWindow()                 # draws one frame: animations step, finished loads show
        if img.isNull():
            raise RuntimeError("snap: the window gave no picture")
        same = same + 1 if last is not None and img == last else 0
        last = img
        if same >= still and (ready is None or ready()) and not loading(win.contentItem()) and not animating(win.contentItem()):
            return img
        if _t.monotonic() > end:
            if may_move:
                return img
            raise RuntimeError(f"snap: the screen was still changing after {limit:g} s (an endless animation, or something "
                               "that keeps loading); no picture taken")
        _t.sleep(0.01)


def save_snap(win, path, **kw) -> None:
    """grab_settled, saved to `path`; a picture that can't be written fails the step."""
    if not grab_settled(win, **kw).save(str(path)):
        raise RuntimeError(f"snap: could not save {path}")


def loading(item) -> bool:
    """Something under `item` is still loading: a picture or an asynchronous Loader with a source and its `progress`
    short of 1, not an inactive one (PySide can't read their `status` enum)."""
    source = item.property("source")             # a QUrl (an Image) or text (a Loader); an empty QUrl is not "a source"
    if hasattr(source, "isEmpty"):
        source = "" if source.isEmpty() else source.toString()
    if item.isVisible() and item.property("active") is not False and str(source or ""):   # an inactive Loader
        # (a menu's side menu, loaded on first use) never loads: not waited for
        p = item.property("progress")
        if isinstance(p, float) and p < 1:
            return True
    return any(loading(c) for c in item.childItems())


def animating(obj) -> bool:
    """Any Animation, Behavior's animation or Transition under `obj` is running and will end (an endless one, loops
    Infinite, is a spinner or a blink: not waited for). Walks `children()` (items and the animations they own)."""
    for o in obj.children():
        name = o.metaObject().className()
        if ("Animation" in name or "Transition" in name) and o.property("running") is True and o.property("loops") != -2:
            return True
        if animating(o):
            return True
    return False
