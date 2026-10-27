"""The Clay tool's drag (clay_tool_qt.py's ClayTool): a left drag with a brush chosen. The press asks the engine to begin a
stroke there (`sculpt` begin, CL1 CONTRACT § 4); its answer says whether it landed on the clay. On the clay every
pointer move is a dab (`sculpt` dab), shown live; on empty space the same drag turns the view instead (as in Nomad: no
hunting for the middle button), and a press and release without moving there is a click (it selects what is there).
One request at a time on the viewport's engine thread: while the engine works, the new pointer positions wait and go
together in the next request (none are dropped: the engine spaces the dabs along them), so it never falls behind.
The release ends the stroke (`sculpt` end writes the dabs file) and makes one `clay.stroke(dabs=<ref>)`: one undo step.
The whole drag uses the scene and camera of its press. Each answer's times are kept in `timings` (tools/clay_walk.py).
Ctrl held at the press = the opposite (clay_ring.opposite: Add <-> Carve swap the brush; Flatten, Crease and Mask send
`invert`, which the stroke step keeps); Shift = Smooth. A pen's pressure is each point's third value ([x, y, p]); a
mouse's points have two. Falloff, Spacing and Front faces only come from the clay like Size and Strength.
`_send` is the one place a request is made (CL2's lead swaps its request for the dab + picture one).
"""
from __future__ import annotations

import time

from PySide6.QtCore import Slot

from . import clay_ring as R
from . import dab_trace

WORDS = {"add": "Add", "carve": "Carve", "smooth": "Smooth", "pull": "Pull", "flatten": "Flatten", "crease": "Crease",
         "mask": "Mask"}
UNDO = {"flatten": "Puff out", "crease": "Ridge", "mask": "Unmask"}     # a stroke with `invert`, in the History


def _sculpt(eng, req):
    ask = getattr(eng, "sculpt", None)                    # Engine.sculpt (member B); the raw request until it lands
    return ask(**req) if ask is not None else eng._request({"sculpt": req})


class ClayStroke:
    def _stroke_reset(self):
        self._phase, self._busy, self._up, self._ending = "", False, True, False
        self._pending, self._moved, self.timings = [], False, []
        self._scene = self._cam = self._stroke = None

    # --- from QML: logical px and the screen's device pixel ratio
    @Slot(float, float, float, bool, bool, float)
    def press(self, x, y, dpr, ctrl, shift, pressure=-1.0):
        if not self.sculpts or self._ending or self.v._size is None or self._sizing:
            return
        self._drag += 1
        self._dpr, self._start, self._last, self._moved = dpr, (x, y), (x, y), False
        self._phase, self._busy, self._up, self._pending, self.timings = "wait", False, False, [], []
        self._scene, self._cam = self.v.sent()             # one scene for the whole drag: the engine loads it once
        it = self._item()
        brush, invert = R.opposite(it.get("brush", "add"), ctrl, shift)
        self._stroke = {"brush": brush, "invert": invert, "size": it.get("brushSize", 0.03),
                        "strength": it.get("brushStrength", 0.5), "symmetry": it.get("symmetry", "x"),
                        "accumulate": bool(it.get("accumulate", False)), "falloff": it.get("brushFalloff", 0.5),
                        "spacing": it.get("brushSpacing", 0.3), "frontOnly": bool(it.get("frontOnly", True))}
        self.strokeBrushChanged.emit()
        self._send("begin", [self._px(x, y, pressure)])

    @Slot(float, float, float)
    def move(self, x, y, pressure=-1.0):
        if self._up or self._phase == "":
            return
        self._moved = self._moved or abs(x - self._start[0]) + abs(y - self._start[1]) > 3
        dx, dy, self._last = x - self._last[0], y - self._last[1], (x, y)
        self._shift_ring(x, y)
        if self._phase == "orbit":
            return self.v.orbit(dx, dy)
        if not self._pending:
            self._t_first = dab_trace.now()                 # the oldest move a request carries (dab_trace.py)
        self._pending.append(self._px(x, y, pressure))
        if self._phase == "sculpt" and not self._busy:
            self._send("dab", self._take())

    @Slot()
    def release(self):
        if self._up:
            return
        self._up = True
        if self._phase == "orbit":
            return self._orbit_done()
        if self._phase == "sculpt" and not self._busy:
            self._end()

    @Slot()
    def cancel(self):
        """The drag was taken away (the window lost the mouse): the stroke is put back, nothing is recorded."""
        if self._phase in ("wait", "sculpt"):
            self._drag += 1
            self._send("cancel", [], answer=False)
        self._phase, self._up = "", True
        self.strokeBrushChanged.emit()

    # --- inside
    def _px(self, x, y, pressure=-1.0):
        """A point for the engine: picture px, and a pen's pressure as a third value (none for a mouse)."""
        pt, p = [round(x * self._dpr * self.v._scale, 1), round(y * self._dpr * self.v._scale, 1)], R.pressure(pressure)
        return pt if p is None else [*pt, p]

    def _take(self):
        pts, self._pending = self._pending, []
        return pts

    def _send(self, phase, points, answer=True):
        drag, req = self._drag, {"item": self.clayId, "phase": phase, **self._cam, "points": points,
                                 "brush": self._stroke["brush"], "size": self._stroke["size"],
                                 "strength": self._stroke["strength"], "mirror": self._stroke["symmetry"] != "off",
                                 "accumulate": self._stroke["accumulate"], "invert": self._stroke["invert"],
                                 "falloff": self._stroke["falloff"], "spacing": self._stroke["spacing"],
                                 "frontOnly": self._stroke["frontOnly"]}
        if phase == "end":
            req["folder"] = str(self.b.doc.folder or "")
        scene, self._busy = self._scene, answer
        # a dab and its picture in one request (CL2): the picture drawn right after the dab, never queued behind the
        # next pointer event; the Final look (Cycles) keeps its own progressive pictures
        view = self.v._request() if phase in ("begin", "dab") and not self.v.final.on else None
        worker = self.v._r
        rec = {"tMove": getattr(self, "_t_first", dab_trace.now()), "tSend": dab_trace.now(), "phase": phase,
               "brush": self._stroke["brush"], "points": len(points)} if dab_trace.on() and view is not None else None
        if self.v.link is not None:                       # the window draws the view: straight to it, no worker hop
            return self._post(drag, phase, req, scene, view, rec, answer, len(points))

        def job(eng):
            t0 = time.perf_counter()
            try:
                if rec is not None:
                    rec["tJob"] = dab_trace.now()
                eng.ensure_scene(scene)
                t1 = time.perf_counter()
                if view is None:
                    out = _sculpt(eng, req)
                else:
                    if rec is not None:
                        rec["tEng0"] = dab_trace.now()
                    out, pic = eng.sculpt_view(view, **req)
                    if rec is not None:
                        rec["tEng1"] = dab_trace.now()
                        rec.update({k: out.get(k) for k in ("dabMs", "dabs", "applyMs", "meshMs", "usdMs", "blocks")})
                        if pic is not None:
                            t = pic[4].get("timing", {})
                            rec.update(drawMs=t.get("drawMs"), totalMs=t.get("totalMs"), perf=pic[4].get("perf"))
                    if pic is None and out.get("pictured") and rec is not None and dab_trace.RECORDS is not None:
                        rec.update({k: out.get(k) for k in ("frame", "tRender0", "tRender1")})   # drawn in the window
                        dab_trace.RECORDS.append(rec)
                    if pic is not None:
                        serial = worker.show(*pic, trace=rec)
                        out["pictured"] = True
                        del pic
                        if rec is not None and dab_trace.RECORDS is not None:
                            rec["serial"] = serial
                            dab_trace.RECORDS.append(rec)
                if isinstance(out, dict):
                    out["ensureMs"], out["askMs"] = (t1 - t0) * 1000, (time.perf_counter() - t1) * 1000
            except Exception as e:  # noqa: BLE001  said on the status line, never a silent miss
                out = str(e)
            if answer:
                self.sculpted.emit((drag, phase, out, (time.perf_counter() - t0) * 1000, len(points)))
        self.v._r.call(job)

    def _post(self, drag, phase, req, scene, view, rec, answer, n):
        """`_send` to the window's own view (view_item.py): posted from this thread, answered here when the render
        thread has done the dab and drawn the picture after it (in the same frame)."""
        t0, link = time.perf_counter(), self.v.link
        if rec is not None:
            rec["tJob"] = rec["tEng0"] = dab_trace.now()

        def then(out):
            if isinstance(out, dict):
                v = out.pop("view", None)
                if v is not None:
                    out["pictured"] = True
                    link.drawn.emit({**v, "frame": out.get("frame")})
                if rec is not None and v is not None and dab_trace.RECORDS is not None:
                    t = v.get("timing", {})
                    rec.update({k: out.get(k) for k in ("dabMs", "dabs", "applyMs", "meshMs", "usdMs", "blocks",
                                                        "frame", "tRender0", "tRender1")})
                    rec.update(tEng1=dab_trace.now(), drawMs=t.get("drawMs"), totalMs=t.get("totalMs"),
                               lightMs=t.get("lightMs"), stormMs=t.get("stormMs"))
                    dab_trace.RECORDS.append(rec)
            if answer:
                self._on_sculpted((drag, phase, out, (time.perf_counter() - t0) * 1000, n))
        link.post({"sculpt": {**req, "view": view} if view is not None else req}, then, scene=scene)

    def _on_sculpted(self, answer):
        drag, phase, r, wall, n = answer
        if phase == "end":
            return self._ended(r)
        if drag != self._drag:
            return
        self._busy = False
        if isinstance(r, str):
            self._phase, self._up = "", True
            self.strokeBrushChanged.emit()
            return self.b.fail_line(f"Error: clay: {r}")
        self.timings.append({"phase": phase, "wallMs": round(wall, 2), "engineMs": float(r.get("ms", 0.0)),
                             "points": n, "dabs": r.get("dabs", 0), "ensureMs": round(r.get("ensureMs", 0), 2),
                             "askMs": round(r.get("askMs", 0), 2)})
        if phase == "begin" and not r.get("hit"):           # not on the clay: this drag turns the view
            self._send("cancel", [], answer=False)
            self._phase, self._pending = "orbit", []
            self.strokeBrushChanged.emit()
            if self._moved:
                self.v.orbit(self._last[0] - self._start[0], self._last[1] - self._start[1])
            return self._orbit_done() if self._up else None
        self._phase = "sculpt"
        if not r.get("pictured"):
            self.v.redraw()                                 # the changed blocks, drawn (when no picture came along)
        if self._pending:
            return self._send("dab", self._take())
        if self._up:
            self._end()

    def _orbit_done(self):
        self._phase = ""
        if not self._moved:                                 # a click on something else: select it (as the viewport's click)
            self.v.click(self._start[0] * self._dpr, self._start[1] * self._dpr)

    def _end(self):
        self._phase, self._ending = "", True
        self._send("end", [])

    def _ended(self, r):
        self._ending, self._busy = False, False
        self.strokeBrushChanged.emit()
        if isinstance(r, str):
            self.v.redraw()
            return self.b.fail_line(f"Error: clay: the stroke could not be kept: {r}")
        self.timings.append({"phase": "end", "engineMs": float(r.get("ms", 0.0)), "count": r.get("count", 0)})
        ref, s, it = r.get("dabs", ""), self._stroke, self._item()
        if not ref or it is None:                           # nothing landed: no step
            return self.v.redraw()
        args = {"brush": s["brush"], "size": s["size"], "strength": s["strength"], "symmetry": s["symmetry"],
                "accumulate": s["accumulate"], "falloff": s["falloff"], "spacing": s["spacing"],
                "frontOnly": s["frontOnly"], "invert": s["invert"], "dabs": ref}
        word = UNDO[s["brush"]] if s["invert"] else WORDS.get(s["brush"], s["brush"].title())
        self.b._guard(lambda: self.b._apply([{"op": "clay.stroke", "target": [it["id"]], "args": args}],
                                            f"{word} on {self.b.label_of(it)}"))
