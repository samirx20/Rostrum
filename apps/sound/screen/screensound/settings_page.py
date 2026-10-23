"""The Settings page: the person's settings (rostrum_sound.settings) as inspector rows, built from the same field
data and the same kit rows as the inspector (`rows.layout` / `rows.evaluate`), so the rule of individuality holds
here too (Buffer shows only while "Use speakers alone" is on; a device row only when there is one to pick).

Settings are not part of a song, so a change is saved to the settings file at once, not recorded in a song's
history. Device changes reach the player the next time it opens (the page says so). QML sees it as `settingsPage`,
in the shape the kit's Inspector reads (selectedItem, rows, moreOpen, setValue …).
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum_gui import rows
from rostrum_gui.model import RowsModel
from rostrum_sound import settings
from rostrum_sound.settings_fields import FIELDS

DEFAULT_DEVICE = "Windows default"
FOLDERS = {"projects": settings.projects_dir, "models": settings.models_dir}


class SettingsPage(QObject):
    selectionChanged = Signal()
    changed = Signal()
    statusChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._more, self._status = False, ""
        self._static = rows.layout(FIELDS)
        self.model = RowsModel(rows.ROLES, self)
        self._refresh(reset=True)

    # ---- what the kit's Inspector reads ----------------------------------------------------------------------
    @Property("QVariantMap", notify=selectionChanged)
    def selectedItem(self):
        return {"id": "settings", "label": "Preferences", "kind": ""}

    @Property(QObject, constant=True)
    def rows(self):
        return self.model

    @Property(bool, notify=changed)
    def moreOpen(self):
        return self._more

    @Property(str, notify=statusChanged)
    def status(self):
        return self._status

    @Property(str, notify=changed)
    def facts(self):
        """Only a fault worth saying: the sound devices could not be listed."""
        err = getattr(settings, "device_error", "")
        return f"Could not list the sound devices: {err}" if err else ""

    @Slot()
    def toggleMore(self):
        self._more = not self._more
        self._refresh()

    @Slot(str, "QVariant")
    def setValue(self, name, value):
        try:
            if name in FOLDERS and str(value) == str(FOLDERS[name]()):
                value = ""                 # the shown default path is the default, not a choice
            settings.set(name, value)
            self._set_status("Saved. Sound device changes apply the next time the player opens."
                             if name in ("output", "input", "exclusive", "buffer") else "Saved.")
        except Exception as e:  # noqa: BLE001  the refusal, in its own words
            self._set_status(f"Error: {e}")
        self._refresh()

    # A slider drag on a settings number: one save when it lands.
    @Slot(str)
    def beginScrub(self, name):
        pass

    @Slot(str, "QVariant")
    def scrub(self, name, value):
        self._scrub = (name, value)

    @Slot()
    def endScrub(self):
        scrub, self._scrub = getattr(self, "_scrub", None), None
        if scrub:
            self.setValue(*scrub)

    @Slot()
    def cancelScrub(self):
        self._scrub = None

    @Slot(str)
    def toggleAnimate(self, name):        # settings have no keys; the kit only calls this for animatable rows
        pass

    @Slot(str)
    def clearExpression(self, name):
        pass

    @Slot()
    def reload(self):
        """The page opens: read the file again (an agent may have changed it) and the devices plugged in now."""
        settings.devices(refresh=True)
        self._refresh()

    # ---- rows ---------------------------------------------------------------------------------------------------
    def _refresh(self, reset=False):
        values = settings.load()
        out = rows.evaluate(self._static, values, {}, self._more, choices=settings.choices)
        for r in out:                      # an empty device is Windows' own choice, not "None"
            if r["row"] == "param" and r["id"] in ("output", "input"):
                r["options"] = [{**o, "label": DEFAULT_DEVICE} if o["value"] == "" else o for o in r["options"]]
        for r in out:                      # an empty folder shows the real folder it means
            if r["row"] == "param" and r["id"] in FOLDERS and not r["value"]:
                r["value"] = str(FOLDERS[r["id"]]())
        (self.model.reset if reset else self.model.update)(out)
        self.changed.emit()

    def _set_status(self, text):
        self._status = text
        self.statusChanged.emit()
