"""Export, from the screen (the Export sheet, ExportSheet.qml): the same versioned render the MCP `render_mix` makes (`handoff.render`:
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
from rostrum_sound import deliver, handoff

from . import playback


def summary(r: dict) -> str:
    n_bus, n_track = len(r.get("busStems") or {}), len(r.get("stems") or {})
    stems = (f"{n_track} track stems" + (f" + {n_bus} group stems" if n_bus else "")) if n_track or n_bus else "no stems"
    cut = f", {r['songSeconds'] - r['seconds']:.1f} s of silence trimmed" if r.get("trimmed") else ""
    return (f"Version {r['version']} · {r.get('format', {}).get('label', '')}, {r.get('sampleRate', 0) / 1000:g} kHz · "
            f"{r['seconds']:.1f} s{cut} · {stems}")


def option_label(c: dict) -> str:
    return f"{c['label']} — {c['detail']}"


def files_of(r: dict) -> list[dict]:
    """What the render wrote, for the list on screen: [{label, path}] — the mix, then the stems (tracks, then buses)."""
    return ([{"label": "Mix", "path": r["file"]}]
            + [{"label": f"Track · {k}", "path": p} for k, p in (r.get("stems") or {}).items()]
            + [{"label": f"Group · {k}", "path": p} for k, p in (r.get("busStems") or {}).items()])


class RenderExport(QObject):
    changed = Signal()
    dialogChanged = Signal()
    _done = Signal("QVariantMap", str)         # the render answer or the error line (from the worker thread)

    def __init__(self, bridge, open_engine=playback.open_engine, parent=None):
        super().__init__(parent)
        self.bridge, self._open_engine = bridge, open_engine
        self._busy, self._status, self._result, self._dialog, self._stems = False, "", {}, False, False
        self._format, self._rate, self._trim = deliver.DEFAULT_FORMAT, 0, True      # rate 0: the song's own (48 kHz when not one of ours)
        self._thread: threading.Thread | None = None
        self._done.connect(self._finish)

    # ---- what to deliver: the choices are `deliver`'s data (the same list render_mix offers); a rate the format cannot
    # ---- have is not offered, and a chosen one it cannot have falls back to the song's own
    @Property("QVariantList", constant=True)
    def formats(self):
        return [{"value": c["id"], "label": option_label(c)} for c in deliver.choices()["formats"]]

    @Property("QVariantList", notify=changed)
    def rates(self):
        return [{"value": str(c["id"]), "label": option_label(c)} for c in deliver.rates_for(self._format)]

    @Property(str, notify=changed)
    def format(self):
        return self._format

    @Property(str, notify=changed)
    def rate(self):
        return str(self.options().sample_rate)

    @Property(bool, notify=changed)
    def stems(self):
        """Also a file for every track and group (off by default: most deliveries are the mix alone)."""
        return self._stems

    @Slot(bool)
    def setStems(self, on):
        self._stems = bool(on)
        self.changed.emit()

    @Property(bool, notify=dialogChanged)
    def dialogOpen(self):
        """Whether the Export sheet is open: one flag, so the top bar, Ctrl+E and a scripted step all open the
        same sheet."""
        return self._dialog

    @Slot(bool)
    def setDialogOpen(self, on):
        if on != self._dialog:
            self._dialog = on
            self.dialogChanged.emit()

    @Property(bool, notify=changed)
    def trim(self):
        return self._trim

    def options(self) -> deliver.Options:
        """The choices as the render takes them; a rate the format cannot have gives way to the song's own."""
        doc_rate = self.bridge.doc.data.get("sampleRate", 48000)
        rate = self._rate or doc_rate
        if rate not in [r["id"] for r in deliver.rates_for(self._format)]:
            rate = 0
        return deliver.Options.read({"format": self._format, "sampleRate": rate or None, "trim": self._trim}, doc_rate)

    @Slot(str)
    def setFormat(self, value):
        self._format = value
        self.changed.emit()

    @Slot(str)
    def setRate(self, value):
        self._rate = int(value)
        self.changed.emit()

    @Slot(bool)
    def setTrim(self, on):
        self._trim = bool(on)
        self.changed.emit()

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
        self._busy, self._status, self._result = True, "Exporting the mix" + (" and stems…" if self._stems else "…"), {}
        self.changed.emit()
        who = f"{self.bridge.who.kind}:{self.bridge.who.name}"
        self._thread = threading.Thread(target=self._work, args=(doc, schedule, who, self.options(), "all" if self._stems else []),
                                        daemon=True)
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

    def _work(self, doc, schedule, who, opts, stems):
        eng = None
        try:
            eng = self._open_engine()
            r = handoff.render(doc.folder, doc, eng, schedule, who, stems=stems,
                               options={"format": opts.format, "sampleRate": opts.sample_rate, "trim": opts.trim})
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
