"""The ≡ menu's rows and Ctrl+K's file commands, from what applies now (absent, never greyed; INTERACTION.md 1.19):
New, Open…, Open recent ▸, Duplicate…, Save a version, Show folder, Start screen…, then the app's own rows (QML adds
those). A slot mix-in for ProjectFiles; QML calls `menu()` when it opens and `pick(value)` with what was chosen."""
from __future__ import annotations

from PySide6.QtCore import Slot

ASKS = ("open", "duplicate", "version", "find")  # these need the window first (a dialog, History's name field)


class FileMenuSlots:
    @Slot(result="QVariantList")
    def menu(self):
        k, rows = self._keys, self._rows()
        out = [{"value": "new", "label": "New", "keys": k["new"], "group": "open"},
               {"value": "open", "label": "Open…", "keys": k["open"], "group": "open"}]
        if rows:
            out.append({"value": "recent", "label": "Open recent", "group": "open",
                        "sub": [{"value": f"recent:{i}", "label": r["name"], "keys": r["when"], "group": "recent"}
                                for i, r in enumerate(rows)]})
        if self.kind.sample:
            out.append({"value": "sample", "label": "Open sample", "group": "open"})
        if self.has_project():
            out += [{"value": "duplicate", "label": "Duplicate…", "keys": k["duplicate"], "group": "file"},
                    {"value": "version", "label": "Save a version", "keys": k["version"], "group": "file"},
                    {"value": "folder", "label": "Show folder", "group": "file"},
                    {"value": "start", "label": "Start screen…", "group": "file"}]
        if self._rescue:
            out.append({"value": "rescue", "label": "Open the last version that works", "group": "repair"})
        if self._missing():
            out.append({"value": "find", "label": "Find missing files…", "group": "repair"})
        return out

    def commands(self) -> list[dict]:
        """Ctrl+K's rows ({key, label, hint}): the menu's, flat."""
        out = []
        for e in self.menu():
            for row in e.get("sub") or [e]:
                label = f"Open {row['label']}" if row["value"].startswith("recent:") else row["label"]
                hint = "Recent" if row["value"].startswith("recent:") else row.get("keys", "")
                out.append({"key": f"file:{row['value']}", "label": label, "hint": hint})
        return [c for c in out if c["key"] != "file:recent"]

    @Slot(str, result=bool)
    def pick(self, value):
        """A row chosen (the menu, Ctrl+K as "file:<value>", a key). What needs the window goes back as `wanted`."""
        value = value.removeprefix("file:")
        if value in ASKS:
            self.wanted.emit(value)
            return True
        if value.startswith("recent:"):
            return self.openRecent(int(value.split(":")[1]))
        go = {"rescue": self.openRescued, "new": self.newProject, "sample": self.openSample, "copy": self.openCopy,
              "folder": lambda: self.showFolder() or True, "start": lambda: self.setStart(True) or True}.get(value)
        return bool(go and go())
