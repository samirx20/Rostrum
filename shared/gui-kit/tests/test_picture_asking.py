"""Inside `asking()` a question goes to the engine before a picture asked just before it, and that picture is still
drawn when the block ends (frames.py; a held picture that never came would leave the canvas showing an old one)."""
import threading

from rostrum_gui.frames import PictureWorker


class Worker(PictureWorker):
    def __init__(self):
        super().__init__("test-pictures")
        self.done, self.drawn = [], threading.Event()

    def open_engine(self):
        return object()

    def handle(self, eng, job):
        if job[0] == "ask":
            job[1].set()
        self.done.append(job[0])
        if job[0] == "picture":
            self.drawn.set()


def test_the_question_goes_first_and_the_held_picture_follows():
    w = Worker()
    w.start()
    try:
        answered = threading.Event()
        with w.asking():
            w.post_latest(("picture",))
            w.post_ordered(("ask", answered))
            assert answered.wait(5)
            assert w.done == ["ask"]                # the picture waits while asking
        assert w.drawn.wait(5)
        assert w.done == ["ask", "picture"]
    finally:
        w.close()
