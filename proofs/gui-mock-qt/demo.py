"""Plays demo.json against the document: the same two operations a click makes."""
import json
import sys
import time

from PySide6.QtCore import QTimer


def apply(doc, op):
    """One demo step -> one document operation. An unknown op/item/control raises (the caller exits nonzero)."""
    if op["op"] == "select":
        doc.select(op["item"])
    elif op["op"] == "set":
        doc.setValue(op["item"], op["param"], op["value"])
    elif op["op"] != "end":
        raise ValueError(f"unknown op {op!r}")


class Player:
    def __init__(self, app, win, doc, code):
        self.app, self.win, self.doc, self.code = app, win, doc, code

    def run(self, fn):
        """Run fn; any error ends the app with a nonzero code and a message."""
        try:
            fn()
        except Exception as e:  # noqa: BLE001  fail loudly, whatever it was
            print(f"FAIL: {e!r}", file=sys.stderr)
            self.code[0] = 3
            self.app.exit(3)

    def moment(self, ops, png, visible_json):
        def go():
            for op in ops:
                apply(self.doc, op)
            if visible_json:
                shown, more = self.doc.visible()
                json.dump({"item": self.doc.sel, "shown": shown, "more": more}, open(visible_json, "w", encoding="utf-8"), indent=2)
            QTimer.singleShot(500, lambda: self.run(lambda: self.shoot(png)))  # let the reveal finish
        self.run(go)

    def shoot(self, png):
        if png:
            img = self.win.grabWindow()
            if not img.save(png):
                raise RuntimeError(f"could not save {png}")
            print(f"saved {png} {img.width()}x{img.height()}")
        self.app.quit()

    def record(self, steps, folder):
        """Real-time: run each step at its time, grab frames as fast as the window allows, then write a concat list
        (each frame lasts until the next) so ffmpeg can resample it to an exact 30 fps."""
        folder.mkdir(parents=True, exist_ok=True)
        t0 = time.perf_counter()
        pending, frames = list(steps), []

        def tick():
            now = time.perf_counter() - t0
            while pending and pending[0]["at"] <= now:
                apply(self.doc, pending.pop(0))
            if not pending:  # the "end" step has run
                lines = ["ffconcat version 1.0"]
                for i, (t, name) in enumerate(frames):
                    lines += [f"file '{name}'", f"duration {(frames[i + 1][0] if i + 1 < len(frames) else now) - t:.4f}"]
                lines.append(f"file '{frames[-1][1]}'")
                (folder / "frames.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
                print(f"{len(frames)} frames in {now:.2f} s = {len(frames) / now:.1f} fps captured")
                self.app.quit()
                return
            name = f"f{len(frames):05d}.bmp"
            self.win.grabWindow().save(str(folder / name))
            frames.append((now, name))
            QTimer.singleShot(0, lambda: self.run(tick))

        self.run(tick)
