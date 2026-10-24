"""Send to 2D on the screen (SPEC §12, §11.3): QML's `sender` (backend.sender too). The work is rostrum3d/send.py, the same
code as the agents' render_send_shot, so the link is the same 2D step whoever sends.

    sender.scenes()                        -> [{value "<2D item>/<scene id>", label, in}]: the menu of 2D scenes
    sender.send(shotId, target, scene)     -> "" when sent, else the plain error line (also shown in the status line)

scene "" = the scene this shot was sent to before, else the project's only 2D scene (several: the menu must pass one).
A shot with no render of the scene as it is now is added to the Render page's queue first (render.queue.add, first in
line); when that job is done the send runs by itself. target "editor" fails loudly: the Editor isn't built yet.
"""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot
from rostrum_core import RostrumError

from rostrum3d import send


class Sender(QObject):
    sent = Signal(str)                       # the status line's words after a send

    def __init__(self, bridge, parent=None):
        super().__init__(parent or bridge)
        self._b, self._waiting = bridge, {}      # {queue job id: (shot, target, scene)}
        queue = getattr(bridge, "queue", None)
        if queue is not None:
            queue.changed.connect(self._after_render)

    @Slot(result="QVariantList")
    def scenes(self):
        try:
            return [{"value": s["value"], "label": s["label"], "in": s["in"]} for s in send.scenes(self._b.doc.folder)] if self._b.doc.folder else []
        except RostrumError as e:
            self._b.fail_line(e.line())
            return []

    @Slot(str, str, str, result=str)
    def send(self, shot_id, target, scene):
        return self._send(shot_id, target, scene, True)

    def _send(self, shot_id, target, scene, may_render) -> str:
        b = self._b
        try:
            out = send.send_shot(b.doc.folder, b.doc, shot_id, target or "2d", scene or None, b.who)
        except send.NeedsRender as e:
            if may_render:
                return self._render_first(shot_id, target, scene)
            b.fail_line(e.line())                # rendered, yet not usable (no EXR frames, or the scene changed meanwhile)
            return e.line()
        except RostrumError as e:
            b.fail_line(e.line())
            return e.line()
        l = out["link"]
        words = f'{shot_id} sent to 2D · {l["scene"]} ({"new 3D render layer" if l["made"] else "same layer, newest render"})'
        b.say(words)
        self.sent.emit(words)
        return ""

    def _render_first(self, shot_id, target, scene) -> str:
        b = self._b
        try:
            send.pick(b.doc.folder, b.doc.item_id, shot_id, scene or None)      # a scene that can't be sent to says so now
        except RostrumError as e:
            b.fail_line(e.line())
            return e.line()
        queue = getattr(b, "queue", None)
        if queue is None:
            line = f"Error: {shot_id} has no render of the scene as it is now: render it, then Send to 2D again"
            b.fail_line(line)
            return line
        job = queue.renderNow(shot_id)
        if job:
            self._waiting[job] = (shot_id, target, scene)
            b.say(f"{shot_id}: rendering first, then it goes to 2D")
        return ""

    def _after_render(self):
        rows = {r["id"]: r for r in self._b.queue.rows}
        for job, (shot_id, target, scene) in list(self._waiting.items()):
            status = rows.get(job, {}).get("status")
            if status in ("done", "failed", "cancelled"):
                del self._waiting[job]
                if status == "done":
                    self._send(shot_id, target, scene, False)
