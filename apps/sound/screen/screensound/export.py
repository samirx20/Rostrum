"""Render mix and stems, from the screen: the same versioned render the MCP `render_mix` makes (`handoff.render`:
`renders/<item>/vNNN/` with its manifest, every track's stem, and a stem per bus when the engine writes them), in the
background on its own engine process. Exposed to QML as `mixer.export`. A failure is written in the status, in
words, and is the bridge's red error too (never a quiet "done").
"""
from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices
from rostrum_core import RostrumError
from rostrum_sound import compile as compile_doc
from rostrum_sound import handoff

from . import playback


def summary(r: dict) -> str:
    n_bus = len(r.get("busStems") or {})
    parts = [f"version {r['version']}", f"{len(r.get('stems') or {})} track stems"] + ([f"{n_bus} bus stems"] if n_bus else [])
    return "Rendered " + ", ".join(parts)


def files_of(r: dict) -> list[dict]:
    """What the render wrote, for the list on screen: [{label, path}] — the mix, then the stems (tracks, then buses)."""
    return ([{"label": "Mix", "path": r["file"]}]
            + [{"label": f"Track · {k}", "path": p} for k, p in (r.get("stems") or {}).items()]
            + [{"label": f"Bus · {k}", "path": p} for k, p in (r.get("busStems") or {}).items()])


class RenderExport(QObject):
    changed = Signal()
    _done = Signal("QVariantMap", str)         # the render answer or the error line (from the worker thread)

    def __init__(self, bridge, open_engine=playback.open_engine, parent=None):
        super().__init__(parent)
        self.bridge, self._open_engine = bridge, open_engine
        self._busy, self._status, self._result = False, "", {}
        self._thread: threading.Thread | None = None
        self._done.connect(self._finish)

    @Property(bool, notify=changed)
    def busy(self):
        return self._busy

    @Property(str, notify=changed)
    def status(self):
        return self._status

    @Property(str, notify=changed)
    def folder(self):
        return self._result.get("folder", "")

    @Property("QVariantList", notify=changed)
    def files(self):
        return files_of(self._result) if self._result else []

    @Slot(result=bool)
    def start(self):
        """Begin the render; false (with the reason as the error) when it can't start."""
        if self._busy:
            return False
        doc = self.bridge.doc
        if not doc.folder or not doc.item_id:
            return self._refuse("Error: render: save the song into a project first (open it with a project folder), so the render has a place to go")
        try:
            schedule = compile_doc(doc)
        except RostrumError as e:
            return self._refuse(f"Error: render: {e.line()}")
        self._busy, self._status, self._result = True, "Rendering the mix and stems…", {}
        self.changed.emit()
        who = f"{self.bridge.who.kind}:{self.bridge.who.name}"
        self._thread = threading.Thread(target=self._work, args=(doc, schedule, who), daemon=True)
        self._thread.start()
        return True

    @Slot()
    def reveal(self):
        """Open the version folder in the file browser."""
        if self.folder:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.folder))

    def close(self):
        if self._thread is not None:
            self._thread.join(timeout=120)

    def _work(self, doc, schedule, who):
        eng = None
        try:
            eng = self._open_engine()
            r = handoff.render(doc.folder, doc, eng, schedule, who)
            if not Path(r["file"]).is_file():
                raise RuntimeError(f"the mix is not at {r['file']}")
            out = (r, "")
        except Exception as e:  # noqa: BLE001  shown on the screen, whatever it was
            out = ({}, f"Error: render: {getattr(e, 'line', lambda: e)()}")
        finally:
            if eng is not None:
                eng.close()
        self._done.emit(*out)

    def _finish(self, result, error):
        self._busy = False
        if error:
            self._status = error
            self.bridge._fail(error)
        else:
            self._result, self._status = dict(result), summary(result)
        self.changed.emit()

    def _refuse(self, line):
        self._status = line
        self.changed.emit()
        self.bridge._fail(line)
        return False
