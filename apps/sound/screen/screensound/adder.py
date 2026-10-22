"""The "+ Track" button: what a person can add, each one `track.add` call (one undo step, what an agent would call),
then the new track is selected so its card / piano roll / inspector shows it. The instrument is only a starting
point: the card changes it. Exposed to QML as `adder`.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Slot

# key, label, the track's fields (doc/playing.py: instrument forms; names.BUILT_INS)
ENTRIES = [
    ("piano", "Piano", {"name": "Piano", "instrument": "builtIn", "builtIn": "grandPiano"}),
    ("strings", "Strings", {"name": "Strings", "instrument": "builtIn", "builtIn": "analogStrings"}),
    ("pad", "Pad", {"name": "Pad", "instrument": "builtIn", "builtIn": "warmPad"}),
    ("bass", "Bass", {"name": "Bass", "instrument": "builtIn", "builtIn": "subBass"}),
    ("synth", "Synth", {"name": "Synth", "instrument": "synth"}),
    ("drums", "Drums", {"name": "Drums", "instrument": "kit"}),
    ("voice", "Voice (spoken lines)", {"name": "Voice", "instrument": "voice"}),
    ("audio", "Audio (recordings, sound files)", {"name": "Audio", "instrument": "none"}),
]


class Adder(QObject):
    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.bridge = bridge

    @Property("QVariantList", constant=True)
    def entries(self):
        return [{"value": k, "label": label} for k, label, _ in ENTRIES]

    @Slot(str)
    def add(self, key):
        fields = next(f for k, _, f in ENTRIES if k == key)
        b = self.bridge

        def go():
            before = {t["id"] for t in b.doc.data.get("tracks", [])}
            b._apply([{"op": "track.add", "args": dict(fields)}], f"Add {fields['name'].lower()} track")
            new = [t["id"] for t in b.doc.data.get("tracks", []) if t["id"] not in before]
            if new:
                b.select(new[0])
        b._guard(go)
