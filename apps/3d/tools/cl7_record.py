# CL7 walk helpers: a paced scripted hand (QTest on the window, its position kept for the pointer drawn on the video), a
# step clock (each step's time from its first input until the app showed its result, the app's own waits inside it, the
# releases and discrete feedback timed), and a recorder (the window's own pixels on a timer, the pointer and the step's
# caption drawn on each frame in a worker thread, ffmpeg after).
import os
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PySide6.QtCore import QObject, QPoint, QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtTest import QTest

import clay_walk as W

QUIET_MS = 200            # a discrete action that shows nothing for longer than this is flagged


class Hand:
    """A quick person's hand: glides of ~0.5-1 s at 60 moves a second, small pauses, the position kept."""

    def __init__(self, win, clock):
        self.win, self.clock, self.pos, self.down = win, clock, QPointF(8, 8), False

    def _move(self, p):
        self.pos = QPointF(p)
        QTest.mouseMove(self.win, QPoint(round(p.x()), round(p.y())))

    def glide(self, to, secs=0.6):
        self.clock.touch()
        a, b = QPointF(self.pos), QPointF(to)
        n = max(2, int(secs * 60))
        for i in range(1, n + 1):
            t = i / n
            e = t * t * (3 - 2 * t)                                   # ease in and out
            self._move(QPointF(a.x() + (b.x() - a.x()) * e, a.y() + (b.y() - a.y()) * e))
            W.pump(secs / n)

    def click(self, at, secs=0.6, button=Qt.LeftButton, mods=Qt.NoModifier, pause=0.15):
        self.glide(at, secs)
        W.pump(pause)
        self.down = True
        QTest.mouseClick(self.win, button, mods, QPoint(round(at.x()), round(at.y())))
        self.down = False
        return time.perf_counter()

    def click_item(self, item, secs=0.6, **kw):
        return self.click(QPointF(W.centre(item)), secs, **kw)

    def drag(self, pts, secs, button=Qt.LeftButton, mods=Qt.NoModifier, rest=0.15, on_move=None):
        """Press on pts[0], move through the rest over `secs`, let go; returns the release time. on_move(i) after each move."""
        self.glide(pts[0], 0.5)
        W.pump(rest)
        p0 = QPoint(round(pts[0].x()), round(pts[0].y()))
        QTest.mousePress(self.win, button, mods, p0)
        self.down = True
        dt = secs / max(1, len(pts) - 1)
        for i, p in enumerate(pts[1:], 1):
            self._move(p)
            if on_move:
                on_move(i)
            W.pump(dt)
        t = time.perf_counter()
        QTest.mouseRelease(self.win, button, mods, QPoint(round(pts[-1].x()), round(pts[-1].y())))
        self.down = False
        return t

    def key(self, key, mods=Qt.NoModifier):
        self.clock.touch()
        QTest.keyClick(self.win, key, mods)

    def park(self, secs=0.4):
        self.glide(QPointF(8, 8), secs)


class Clock:
    """Steps: name, budget, the real-input time, the app's waits, releases, feedback, checks, stumbles."""

    def __init__(self, rec):
        self.rec, self.steps, self.cur = rec, [], None

    def begin(self, n, name, budget):
        self.cur = {"n": n, "name": name, "budget": budget, "t0": None, "appWait": 0.0, "waits": [], "releases": [],
                    "feedback": [], "checks": [], "stumbles": []}
        if self.rec:
            self.rec.caption = f"{n} · {name}"

    def touch(self):
        if self.cur is not None and self.cur["t0"] is None:
            self.cur["t0"] = time.perf_counter()

    def wait(self, cond, what, timeout=30.0):
        """Wait (pumping) for the app; the time counts as the app's wait. False (and a failed check) on a timeout."""
        t = time.perf_counter()
        ok = W.pump(timeout, cond, what)
        ms = (time.perf_counter() - t) * 1000
        self.cur["appWait"] += ms / 1000
        self.cur["waits"].append({"what": what, "ms": round(ms)})
        if not ok:
            self.check(False, f"timed out ({timeout:.0f} s) waiting for {what}")
        return ok

    def release(self, what, t_release, cond, timeout=30.0):
        """A direct manipulation's release: the time from the let-go until `cond` (the result shown)."""
        ok = W.pump(timeout, cond, what)
        ms = (time.perf_counter() - t_release) * 1000         # (the release itself may hold the GUI thread: counted)
        self.cur["appWait"] += ms / 1000
        self.cur["releases"].append({"what": what, "ms": round(ms), "slow": ms > QUIET_MS, "ok": ok})
        if not ok:
            self.check(False, f"timed out waiting for {what}")
        return ms

    def feedback(self, what, t_click, cond, timeout=10.0):
        """A discrete action: the time from the click until something shows (`cond`); over QUIET_MS is flagged."""
        ok = W.pump(timeout, cond, what)
        ms = (time.perf_counter() - t_click) * 1000
        self.cur["appWait"] += ms / 1000
        self.cur["feedback"].append({"what": what, "ms": round(ms), "quiet": ms > QUIET_MS, "ok": ok})
        if not ok:
            self.check(False, f"nothing showed after {what}")
        return ms

    def check(self, ok, line):
        W.check(ok, f"{self.cur['n']}. {line}" if self.cur else line)
        if self.cur is not None:
            self.cur["checks"].append({"ok": bool(ok), "check": line})
        return ok

    def stumble(self, what, cause="", worst=1):
        """A step that couldn't be done as SPEC § 1 says. `worst`: 3 blocks the step, 2 wrong result / slow, 1 rough."""
        print(f"STUMBLE {self.cur['n']}. {what}")
        self.cur["stumbles"].append({"what": what, "cause": cause, "weight": worst})

    def end(self, picture=None):
        c = self.cur
        t0 = c["t0"] or time.perf_counter()
        c["realS"] = round(time.perf_counter() - t0, 2)
        c["appWaitS"] = round(c.pop("appWait"), 2)
        c.pop("t0")
        c["picture"] = picture
        c["overBudget"] = c["realS"] > c["budget"]
        if c["overBudget"]:
            W.check(False, f"{c['n']}. {c['name']}: {c['realS']} s, over its {c['budget']} s")
        self.steps.append(c)
        self.cur = None


class Recorder(QObject):
    """The window's own pixels at `fps` (grabWindow on a timer), the pointer and the caption drawn on a worker thread,
    saved as numbered JPEGs (numbered by time, so a missed tick repeats the last frame); encode() makes the MP4s."""

    def __init__(self, win, hand, scratch: Path, fps=15):
        super().__init__()
        self.win, self.hand, self.dir, self.fps = win, hand, scratch, fps
        self.caption, self.t0, self.grab_ms, self.every, self.last = "", None, [], 1, -1
        self.dir.mkdir(parents=True, exist_ok=True)
        self.pool = ThreadPoolExecutor(1)
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.timeout.connect(self._tick)

    def start(self):
        self.t0 = time.perf_counter()
        self.timer.start(round(1000 / self.fps))

    def stop(self):
        self.timer.stop()
        self.pool.shutdown(wait=True)

    def _tick(self):
        idx = round((time.perf_counter() - self.t0) * self.fps)
        if idx <= self.last:
            return
        t = time.perf_counter()
        img = self.win.grabWindow()
        self.grab_ms.append((time.perf_counter() - t) * 1000)
        if len(self.grab_ms) == 30 and sum(self.grab_ms) / 30 > 30 and self.every == 1:   # too dear: every 2nd frame
            self.every = 2
            self.timer.setInterval(round(2000 / self.fps))
        self.last = idx
        dpr = self.win.devicePixelRatio()
        self.pool.submit(self._save, img, idx, QPointF(self.hand.pos) * dpr, self.hand.down, self.caption, dpr)

    def _save(self, img, idx, at, down, caption, dpr):
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing)
        arrow = QPainterPath()                                    # a plain pointer arrow, tip at the hand
        s = 1.4 * dpr
        for i, (x, y) in enumerate(((0, 0), (0, 17), (4.5, 13), (7.5, 20), (10, 19), (7, 12), (12.5, 12), (0, 0))):
            pt = QPointF(at.x() + x * s, at.y() + y * s)
            arrow.moveTo(pt) if i == 0 else arrow.lineTo(pt)
        if down:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 160, 40, 110))
            p.drawEllipse(at, 14 * dpr, 14 * dpr)
        p.setPen(QPen(QColor(0, 0, 0), 1.5 * dpr))
        p.setBrush(QColor(255, 255, 255))
        p.drawPath(arrow)
        if caption:
            f = QFont("Segoe UI")
            f.setPixelSize(round(15 * dpr))
            f.setWeight(QFont.DemiBold)
            p.setFont(f)
            w = p.fontMetrics().horizontalAdvance(caption) + 24 * dpr
            box = QRectF(16 * dpr, img.height() - 52 * dpr, w, 32 * dpr)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(0, 0, 0, 170))
            p.drawRoundedRect(box, 6 * dpr, 6 * dpr)
            p.setPen(QColor(255, 255, 255))
            p.drawText(box, Qt.AlignCenter, caption)
        p.end()
        img.save(str(self.dir / f"f{idx:06d}.jpg"), "JPG", 92)

    def encode(self, out_hq: Path, out_share: Path) -> dict:
        """Fill missed ticks with the frame before, then two MP4s with ffmpeg; the frames are deleted after."""
        files = sorted(self.dir.glob("f*.jpg"))
        if not files:
            return {"error": "no frames"}
        last = int(files[-1].stem[1:])
        prev, filled = None, 0
        for i in range(last + 1):
            f = self.dir / f"f{i:06d}.jpg"
            if f.exists():
                prev = f
            elif prev is not None:
                shutil.copyfile(prev, f)
                filled += 1
        ff = shutil.which("ffmpeg") or ffmpeg_exe()
        src = ["-framerate", str(self.fps), "-start_number", str(int(files[0].stem[1:])), "-i", str(self.dir / "f%06d.jpg")]
        even = "scale=trunc(iw/2)*2:trunc(ih/2)*2"
        runs = {str(out_hq): [ff, "-y", *src, "-vf", even, "-c:v", "libx264", "-preset", "slow", "-crf", "16",
                              "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out_hq)],
                str(out_share): [ff, "-y", *src, "-vf", "scale=w='min(1920,iw)':h='min(1080,ih)':force_original_aspect_ratio=decrease," + even, "-c:v", "libx264", "-preset", "medium",
                                 "-b:v", "8M", "-maxrate", "10M", "-bufsize", "16M", "-pix_fmt", "yuv420p",
                                 "-movflags", "+faststart", str(out_share)]}
        result = {"frames": last + 1, "filled": filled, "fps": self.fps, "every": self.every,
                  "grabMsMean": round(sum(self.grab_ms) / max(1, len(self.grab_ms)), 1),
                  "grabMsMax": round(max(self.grab_ms or [0]), 1)}
        for out, cmd in runs.items():
            r = subprocess.run(cmd, capture_output=True, text=True)
            result[Path(out).name] = "ok" if r.returncode == 0 else r.stderr[-600:]
        shutil.rmtree(self.dir, ignore_errors=True)
        return result


def ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return os.environ.get("FFMPEG", "ffmpeg")
