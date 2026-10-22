"""Rostrum2D's fill of the kit's Export sheet (rostrum_gui/export_sheet.py, EXPORT.md): any export format of the open
composition, through the same code as the MCP tool render_export (rostrum2d.mcp.exporting.run): the same formats, the
same files, the same manifest.

What for, the chosen format's settings (only the ones that apply: export_rows.py, from io/formats.py data), the range
(everything, or marker to marker), where it goes. A press snapshots the scene: edits made while it runs are not in the
file. Cancel stops the engine (never restarted); a failed or cancelled run leaves no unfinished file (exporting.run).
"""
from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import Property, Signal, Slot
from rostrum2d import project_sound
from rostrum2d.mcp import export_name, exporting
from rostrum_core.mcp.files import RENDER_DIR
from rostrum_gui.export_sheet import ExportSheet

from . import export_rows


class Exporter(ExportSheet):
    own = Signal()                                    # = changed, for this class's own properties

    def __init__(self, bridge, engine_factory=None, parent=None):
        super().__init__(bridge, parent)
        self._engine_factory, self._engine = engine_factory, None
        self.changed.connect(self.own)                # (a subclass's property can't notify on the kit's signal: PySide6 crashes)
        self._comp_id = bridge.comp_id          # the comp shown, until another is picked
        self._choice = "mp4"
        self._values = {}
        self.chose()

    def _row(self) -> dict:
        return exporting.info("export", self._choice)

    def _comp(self) -> dict:
        return self.bridge.doc.item(self._comp_id)

    def _duration(self) -> float:
        return float(self._comp().get("duration", 5.0))

    def _stem(self) -> str:
        return export_name.stem_of(self.bridge.doc, self._comp_id)

    # ---- the kit's questions --------------------------------------------------------------------------------
    def choices_list(self):
        return export_rows.what_for(exporting.formats())

    def ranges_list(self):
        """Everything, then marker to marker (the project's markers inside the composition, in time order)."""
        if not self._row()["range"]:
            return []
        d = self._duration()
        out = [{"value": "all", "label": f"Everything · {d:g} s", "start": 0.0, "end": d}]
        times = sorted((t, n) for n, t in (self.bridge.marks.times if self.bridge.doc.folder else {}).items() if 0 <= t <= d)
        for (t0, a), (t1, b) in zip(times, times[1:]):
            if t1 > t0:
                out.append({"value": f"{a}→{b}", "label": f"{a} → {b} · {t1 - t0:g} s", "start": t0, "end": t1})
        return out

    def default_folder(self):
        base = exporting.project_renders(self.bridge.doc.folder, self.bridge.doc.item_id)
        return str(base) if base else str(RENDER_DIR)

    def file_name(self):
        return self._stem() + ("" if self._row()["sequence"] else self._row()["ext"])

    def replaceable(self):
        return not self._row()["sequence"]           # a folder of frames is never replaced (exporting.run)

    def chose(self):
        """The chosen format's defaults: transparency where it can be carried and the background is transparent, its first
        bit depth, its default quality; for an MP4 of a project with sound, its sound (on)."""
        r = self._row()
        self._values = {"alpha": r["alpha"] and exporting.see_through(self._comp().get("background", "#000000")), "depth": r["depths"][0] if r["depths"] else None, "quality": r["quality"]}
        if self._has_sound():
            self._values["sound"] = True
        if not r["range"]:
            self._range = "all"

    def _has_sound(self) -> bool:
        """An MP4 of a project with sound (a stale main-mix mark: no switch here; the Sound row and the export say it)."""
        try:
            return self._choice == "mp4" and project_sound.song(self.bridge.doc.folder, self._comp().get("soundtrack", "")) is not None
        except Exception:  # noqa: BLE001
            return False

    def begin(self, out, overwrite):
        v, span = self._values, self.range_times() or (0.0, self._duration())
        sound = project_sound.for_export(self.bridge.doc.folder, self._comp().get("soundtrack", ""), self._choice, v.get("sound"))
        s = exporting.settings("export", self._choice, self._duration(), v["alpha"], v["depth"], span[0], span[1], v["quality"],
                               background=self._comp().get("background", "#000000"), sound=sound)
        doc = self.bridge.doc
        return {"scene": exporting.snapshot(doc, self._comp_id, self._choice), "fmt": self._choice, "s": s,
                "folder": doc.folder, "item": doc.item_id, "seq": doc.seq, "name": self._stem(), "out": out,
                "overwrite": overwrite}

    def work(self, p, progress):
        def make_engine():
            self._engine = (self._engine_factory or exporting._engine)()
            return self._engine
        facts = exporting.run("export", p["scene"], p["fmt"], p["s"], p["folder"], p["item"], p["seq"], p["out"],
                              lambda done, total: progress(done / total if total else 0.0), make_engine,
                              name=p["name"], overwrite=p["overwrite"])
        version = Path(facts["file"]).parent.name if p["out"] is None else ""
        size = (facts.get("checked") or {}).get("size")
        return {**facts, "version": version if re.fullmatch(r"v\d+", version) else "",
                "summary": f'{facts["frames"]} frames at {facts["fps"]:g} fps' + (f' · {"×".join(map(str, size))}' if size else "")}

    def stop(self):
        if self._engine is not None:
            self._engine.kill()                       # on purpose: never restarted (engine.py)

    # ---- 2D's own: the composition, the chosen format's settings, what Lottie couldn't carry ------------------
    @Property("QVariantList", notify=own)
    def comps(self):
        """The document's compositions to choose from; empty when there is only one (nothing to choose)."""
        rows = self.bridge.doc.data.get("comps", [])
        return [{"value": c["id"], "label": c.get("name") or c["id"]} for c in rows] if len(rows) > 1 else []

    @Property(str, notify=own)
    def comp(self):
        return self._comp_id

    @Property(str, notify=own)
    def format(self):
        return self._choice

    @Property("QVariantList", notify=own)
    def settings(self):
        return export_rows.settings(self._row(), self._values)

    @Property("QVariantList", notify=own)
    def facts(self):
        """The result in words, read back from the file: [{label, text}]."""
        return export_rows.facts(self._row(), self._result, self.path) if self._state == "done" and self._result else []

    @Property("QVariantList", notify=own)
    def report(self):
        """Lottie: what it couldn't carry, one line each."""
        return list(self._result.get("report") or [])

    @Slot(str)
    def setComp(self, comp_id):
        if not self.running() and self.bridge.doc.has(comp_id) and comp_id != self._comp_id:
            self._comp_id = comp_id
            self.chose()
            self._state, self._note = "", ""
            self.changed.emit()

    @Slot(str)
    def setFormat(self, name):                        # (the old name: scripted steps call it)
        self.setChoice(name)

    @Slot(str, "QVariant")
    def setSetting(self, key, value):
        if self.running() or key not in self._values:
            return
        self._values[key] = {"depth": int, "alpha": bool, "quality": str, "sound": bool}[key](value)
        self.changed.emit()
