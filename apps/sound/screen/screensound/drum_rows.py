"""+ Drum ▾ in the Editor's header on a drum track (a slot mix-in for SoundBridge): the roll's drum rows are the kit's
main ones and the ones the track hits; this adds a row for any other drum its kit plays (screen state, per track, never
the song: a hit placed on the row makes the drum the track's own). `kit_drums` is the one list of what a track's kit
plays; the Drum picker in a hit's settings (inspect.drum_options) reads it too.
"""
from __future__ import annotations

from PySide6.QtCore import Property, Slot
from rostrum_sound import names

from .signals import SoundSignals as S


def kit_drums(track: dict) -> list:
    """The drums a track's kit plays, in the kit's own order (a classic kit: its eight; any other kit: the GM names)."""
    return names.kit_drums(track.get("kit")) if track.get("instrument") == "kit" else names.GM_DRUMS


def extend(roll: dict, extra) -> None:
    """The rows asked for with + Drum, after the roll's own (a drum already shown stays where it is)."""
    if roll.get("kind") == "drums" and extra:
        roll["drums"] = roll["drums"] + [d for d in extra if d not in roll["drums"]]


class DrumRowSlots:
    def _drum_rows(self) -> dict:
        return self.__dict__.setdefault("_drum_rows_", {})

    @Property("QVariantList", notify=S.rollChanged)
    def drumRowChoices(self):
        """+ Drum ▾'s menu: the kit's drums the roll does not show yet, by plain name ([] on anything but drums)."""
        from .inspect import drum_words
        roll = self._view["roll"] if self._view else {}
        if roll.get("kind") != "drums" or not self._track or not self.doc.has(self._track):
            return []
        left = [d for d in kit_drums(self.doc.item(self._track)) if d not in roll.get("drums", [])]
        return [{"value": d, "label": drum_words(d), "keys": "", "group": "drums",
                 **({"heading": "Add a drum row"} if i == 0 else {})} for i, d in enumerate(left)]

    @Slot(str)
    def addDrumRow(self, drum):
        """A row for `drum` in the Editor's drum rows (double-click or Draw on it adds a hit there)."""
        if not self._track or not self.doc.has(self._track) or drum not in kit_drums(self.doc.item(self._track)):
            return self._fail(f'Error: drum row: "{drum}" is not a drum this track\'s kit plays.',
                              "That drum isn't in this track's kit.")
        self._drum_rows().setdefault(self._track, []).append(drum)
        self._send_roll(self._roll(self._view["rows"]))
