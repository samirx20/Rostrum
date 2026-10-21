"""Plug-ins on the screen: the scanned list, "add a plug-in" for an effect chain or an instrument, a plug-in's
settings (generic rows, `plugin_rows.py`) and its own window. Exposed to QML as `mixer.plugins`.

Every change is an operation on the document's `plugin` record: `effect.add` / `track.set` to choose one, `effect.set` /
`track.set` with the changed record for a setting (one drag = one change) and for what the plug-in's window saved
(one change when the window closes). Scanning and the window run on a helper engine process off the screen's
thread; a failure is reported loudly, never swallowed.
"""
from __future__ import annotations

import threading

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum_gui import rows
from rostrum_gui.model import RowsModel

from . import plugin_rows


def spec_of(entry: dict) -> dict:
    """The document's record for a scanned plug-in (settings start at the plug-in's own defaults: none written)."""
    return {"format": entry["format"], "path": entry["path"], "id": entry["id"], "name": entry.get("name") or entry["id"]}


class PluginPanel(QObject):
    """One plug-in effect's or instrument's settings: its rows, and what the panel above them says."""
    changed = Signal()

    def __init__(self, hub, owner_id, parent=None):
        super().__init__(parent)
        self.hub, self._owner, self.more = hub, owner_id, False
        self._rows = RowsModel(rows.ROLES, self)
        self._static: list[dict] = []
        self._key = None
        self._info: dict = {}
        self.refresh()

    @Property(str, constant=True)
    def owner(self):
        return self._owner

    @Property(QObject, constant=True)
    def controls(self):
        return self._rows

    @Property("QVariantMap", notify=changed)
    def info(self):
        return self._info

    def refresh(self):
        item = self.hub.bridge.doc.item(self.owner) if self.hub.bridge.doc.has(self.owner) else None
        spec = (item or {}).get("plugin") or {}
        found = self.hub.entry(spec)
        key = (spec.get("path"), spec.get("id"), bool(found))
        if key != self._key:
            self._static, self._key = plugin_rows.layout(found["params"]) if found else [], key
        evaluated = plugin_rows.evaluate(self._static, spec, self.more)
        self._rows.update(evaluated) if self._rows.rows else self._rows.reset(evaluated)
        self._info = {"name": spec.get("name") or spec.get("id") or "", "vendor": (found or {}).get("vendor", ""),
                      "chosen": bool(spec), "missing": bool(spec) and self.hub.scanned and not found,
                      "hasWindow": bool(found and found.get("hasWindow")), "moreOpen": self.more,
                      "windowOpen": self.hub.window_owner == self.owner, "hasMore": any(r["row"] == "more" for r in self._static)}
        self.changed.emit()


class PluginHub(QObject):
    catalogChanged = Signal()
    selectedChanged = Signal()
    windowChanged = Signal()
    _answered = Signal(str, "QVariantMap")
    _failed = Signal(str)

    def __init__(self, bridge, open_engine, parent=None):
        super().__init__(parent)
        self.bridge, self._open_engine, self._engine = bridge, open_engine, None
        self.catalog: list[dict] = []
        self.scanned, self.scanning, self.window_owner = False, False, ""
        self._panels: dict[str, PluginPanel] = {}
        self._answered.connect(self._window_closed)
        self._failed.connect(self._fail)
        bridge.docChanged.connect(self._refresh)
        bridge.selectionChanged.connect(self.selectedChanged)

    def close(self):
        if self._engine is not None:
            self._engine.close()

    # ---- what is installed -------------------------------------------------------------------------------------
    @Property("QVariantList", notify=catalogChanged)
    def effects(self):
        return self._choices("effect")

    @Property("QVariantList", notify=catalogChanged)
    def instruments(self):
        return self._choices("instrument")

    @Property(bool, notify=catalogChanged)
    def busy(self):
        return self.scanning

    def _choices(self, kind):
        return [{"id": self._key(p), "label": f"{p.get('name') or p['id']}  ·  {p['format'].upper()}"}
                for p in self.catalog if p.get("kind") == kind]

    @staticmethod
    def _key(p):
        return f"{p['path']}|{p['id']}"

    def entry(self, spec: dict) -> dict | None:
        return next((p for p in self.catalog if p["path"] == spec.get("path") and p["id"] == spec.get("id")), None)

    @Slot()
    def scan(self):
        """Ask the engine which plug-ins are installed (once; the lists fill in when it answers)."""
        if self.scanning or self.scanned:
            return
        self.scanning = True
        self.catalogChanged.emit()
        self._thread(self._scan, "plug-in scan")

    def _scan(self):
        found = self._aux().plugins()
        self._answered.emit("scan", {"plugins": found["plugins"], "failed": found.get("failed", [])})

    # ---- choosing one ------------------------------------------------------------------------------------------
    def _by_key(self, key) -> dict:
        return next(p for p in self.catalog if self._key(p) == key)

    @Slot(str, str, result=bool)
    def addEffect(self, owner_id, key):
        """effect.add (effect "plugin") on that track / bus / master (one change), then select the new effect."""
        self.bridge.select(owner_id)
        call = {"op": "effect.add", "target": [owner_id], "args": {"effect": "plugin", "plugin": spec_of(self._by_key(key))}}
        if not self.bridge._guard(lambda: self.bridge._apply([call], "Add plug-in")):
            return False
        self.bridge.select(self.bridge.doc.item(owner_id)["effects"][-1]["id"])
        return True

    @Slot(str, str, result=bool)
    def setInstrument(self, track_id, key):
        """track.set: this track is played by that plug-in (one change)."""
        call = {"op": "track.set", "target": [track_id], "args": {"instrument": "plugin", "plugin": spec_of(self._by_key(key))}}
        return self.bridge._guard(lambda: self.bridge._apply([call], "Choose plug-in instrument"))

    # ---- settings ----------------------------------------------------------------------------------------------
    @Slot(str, result=QObject)
    def panel(self, owner_id):
        if owner_id not in self._panels:
            self._panels[owner_id] = PluginPanel(self, owner_id, self)
        return self._panels[owner_id]

    @Property(QObject, notify=selectedChanged)
    def selectedPanel(self):
        """The settings of the selected item when it is a plug-in effect (the Mix page shows them); else nothing."""
        sel = self.bridge.selected
        item = self.bridge.doc.item(sel) if sel and self.bridge.doc.has(sel) else None
        return self.panel(sel) if item and item["type"] == "effect" and item.get("effect") == "plugin" else None

    @Slot(str, str, "QVariant", result=bool)
    def setParam(self, owner_id, param_id, value):
        """One setting changed: the owner's `plugin` record rewritten (a drag calls this once, when it ends)."""
        item = self.bridge.doc.item(owner_id)
        label = next((p.get("name") for p in (self.entry(item["plugin"]) or {}).get("params", []) if str(p["id"]) == param_id), param_id)
        return self._write(owner_id, plugin_rows.with_param(item["plugin"], param_id, float(value)), f"Set {label}")

    @Slot(str)
    def toggleMore(self, owner_id):
        p = self.panel(owner_id)
        p.more = not p.more
        p.refresh()

    def _write(self, owner_id, spec, label):
        kind = "effect" if self.bridge.doc.item(owner_id)["type"] == "effect" else "track"
        call = {"op": f"{kind}.set", "target": [owner_id], "args": {"plugin": spec}}
        return self.bridge._guard(lambda: self.bridge._apply([call], label))

    # ---- the plug-in's own window --------------------------------------------------------------------------------
    @Slot(str)
    def openWindow(self, owner_id):
        """Open the plug-in's window; when it closes, its state and settings are written as one change."""
        if self.window_owner:
            return
        spec = self.bridge.doc.item(owner_id)["plugin"]
        self.window_owner = owner_id
        self.windowChanged.emit()
        self._refresh()
        self._thread(lambda: self._answered.emit("window:" + owner_id, dict(self._aux().plugin_window(spec))), "plug-in window")

    def _window_closed(self, what, answer):
        if what == "scan":
            self.catalog, self.scanned, self.scanning = answer["plugins"], True, False
            self.catalogChanged.emit()
            return self._refresh()
        owner = what.split(":", 1)[1]
        self.window_owner = ""
        self.windowChanged.emit()
        if self.bridge.doc.has(owner):
            self._write(owner, plugin_rows.after_window(self.bridge.doc.item(owner)["plugin"], answer), "Plug-in window")
        self._refresh()

    # ---- inside ---------------------------------------------------------------------------------------------------
    def _aux(self):
        if self._engine is None:
            self._engine = self._open_engine()
        return self._engine

    def _thread(self, fn, what):
        def run():
            try:
                fn()
            except Exception as e:  # noqa: BLE001  fail loudly: the screen reports it
                self._failed.emit(f"{what}: {e}")
        threading.Thread(target=run, daemon=True).start()

    def _fail(self, line):
        self.scanning, self.window_owner = False, ""
        self.catalogChanged.emit()
        self.windowChanged.emit()
        self.bridge._fail("Error: " + line)
        self._refresh()

    def _refresh(self):
        for owner in [o for o in self._panels if not self.bridge.doc.has(o)]:
            self._panels.pop(owner).deleteLater()
        for p in self._panels.values():
            p.refresh()
        self.selectedChanged.emit()
