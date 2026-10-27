"""The screen never lies (INTERACTION.md 1.21 rule 7): the picture worker says it is behind from the moment a picture
is asked until the newest one is served, and never stays behind after it caught up."""
import threading
import time

from rostrum_gui.frames import PictureWorker


class Slow(PictureWorker):
    def __init__(self):
        super().__init__("test-behind")
        self.go = threading.Event()

    def open_engine(self):
        return self

    def close(self):
        pass

    def handle(self, eng, job):
        self.go.wait(2)
        self.publish(None)


def _until(fn, s=2.0):
    end = time.monotonic() + s
    while not fn() and time.monotonic() < end:
        time.sleep(0.005)
    return fn()


def test_behind_from_the_ask_until_the_newest_picture():
    w = Slow()
    w.start()
    assert not w.behind
    w.post_latest("a")
    assert w.behind                               # at once, on the ask
    w.post_latest("b")                            # a newer one while the first is drawn: still behind
    w.go.set()
    assert _until(lambda: not w.behind) and _until(w.idle)
    w._stop = True
    with w._cv:
        w._cv.notify()
