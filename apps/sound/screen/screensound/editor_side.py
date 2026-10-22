"""Beside the Editor (bottom dock), what the piano roll can't show for the selection's track: a voice track's lines
and Make voice (voice_card.py), a plug-in instrument's settings and its choice. These were on the Instruments
page's cards; with the page gone they follow the track the Editor shows. Exposed to QML as `editorSide`.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot

from .voice_card import VoiceMaker, card_roles


class EditorSide(QObject):
    changed = Signal()

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.bridge = bridge
        self.voice = VoiceMaker(bridge, self)
        for s in (self.voice.changed, bridge.timelineChanged, bridge.docChanged):
            s.connect(self.changed)

    def _track(self) -> dict:
        tid = self.bridge.roll.get("id", "")
        return self.bridge.doc.item(tid) if tid and self.bridge.doc.has(tid) else {}

    @Property("QVariantMap", notify=changed)
    def track(self):
        """{id, isPlugin, isVoice, lines, missing, voiceStatus, voiceBusy, voiceFailed} of the Editor's track."""
        t = self._track()
        return {"id": t.get("id", ""), "isPlugin": t.get("instrument") == "plugin",
                **card_roles(t, self.voice.state(t.get("id", "")))}

    @Slot(str)
    def makeVoice(self, track_id):
        """Make the missing takes of the track's lines (off the screen's thread; the document is not edited)."""
        self.voice.start(track_id)

    def close(self):
        self.voice.close()
