"""The In key ▾ chip's two switches (a slot mix-in for SoundBridge; key_lock.py has the rules): Keep notes in the key and
Only the key's rows. Screen state per window like Snap: never saved, never in the history. The chip exists only on a
notes track while the song has a key (`inKeyChip` is {} otherwise), so a person never sees it greyed.
"""
from __future__ import annotations

from PySide6.QtCore import Property, Signal, Slot
from rostrum_sound.doc import keys as K

from . import key_lock

CHOICES = (("keep", "Keep notes in the key"), ("rows", "Only the key's rows"))


class KeyLockSlots:
    keyLockChanged = Signal()

    @property
    def keepInKey(self) -> bool:
        return bool(self.__dict__.get("_keep_key"))

    @property
    def onlyKeyRows(self) -> bool:
        return bool(self.__dict__.get("_key_rows"))

    @Property("QVariantMap", notify=keyLockChanged)
    def inKeyChip(self):
        """{label, entries} for the header's chip: "In key" while Keep is on, else "Key: D minor"; {} when it doesn't
        belong (not a notes track, or the song has no key)."""
        root = self.doc.data
        if self._view["roll"].get("kind") != "notes" or not key_lock.has_key(root):
            return {}
        key = K.key_for(root, 0.0)               # the key the song starts in
        on = {"keep": self.keepInKey, "rows": self.onlyKeyRows}
        return {"label": "In key" if self.keepInKey else f"Key: {key}",
                "entries": [{"value": v, "label": label, "keys": "", "checked": on[v],
                             **({"heading": key} if i == 0 else {})} for i, (v, label) in enumerate(CHOICES)]}

    @Slot(str)
    def toggleKeyLock(self, which):
        """A row of the In key ▾ menu: its switch flipped. Only the key's rows lays the roll out again."""
        if which not in dict(CHOICES):
            return self._fail(f'Error: In key: "{which}" is not a choice ({", ".join(dict(CHOICES))}).')
        attr = "_keep_key" if which == "keep" else "_key_rows"
        setattr(self, attr, not self.__dict__.get(attr))
        if which == "rows":
            self._send_roll(self._roll(self._view["rows"]))
        self.keyLockChanged.emit()
