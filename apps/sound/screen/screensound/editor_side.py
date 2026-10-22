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
        bridge.voiceWanted.connect(self.voice.start)
        bridge.side = self                                    # the scripted steps reach it (line-type)
        self.voice.changed.connect(bridge._rebuild)             # a line starts or stops being spoken: its block says so          # "Speak again": the new takes are made at once

    def _track(self) -> dict:
        tid = self.bridge.roll.get("id", "")
        return self.bridge.doc.item(tid) if tid and self.bridge.doc.has(tid) else {}

    @Property("QVariantMap", notify=changed)
    def track(self):
        """{id, isPlugin, isVoice, lines, missing, voiceStatus, voiceBusy, voiceFailed} of the Editor's track."""
        t = self._track()
        return {"id": t.get("id", ""), "isPlugin": t.get("instrument") == "plugin",
                **card_roles(t, self.voice.state(t.get("id", "")))}

    @Slot(str, str, result=bool)
    def typeLine(self, track_id, text):
        """Enter in "Type what she says": a line at the playhead (or just after the last line when the playhead is
        before its end), one step, selected; its speech is made at once (DESIGN.md §10 #1: made when you finish
        typing; once, kept)."""
        b, words = self.bridge, text.strip()
        if not words or not b.doc.has(track_id):
            return False
        row = next((r for r in b.tracks if r["id"] == track_id), {"blocks": []})
        ends = [x["t"] + x["dur"] for x in row["blocks"] if x["type"] == "line"]
        at = round(max(b.time, max(ends) + 0.1) if ends and b.time < max(ends) else b.time, 3)
        before = {ln["id"] for ln in b.doc.item(track_id).get("lines", [])}
        if not b._act([{"op": "line.add", "target": [track_id], "args": {"text": words, "at": at}}], "Add line"):
            return False
        new = [ln["id"] for ln in b.doc.item(track_id).get("lines", []) if ln["id"] not in before]
        if new:
            b.select(new[0])
        self.voice.start(track_id)
        return True

    @Slot(str)
    def makeVoice(self, track_id):
        """Make the missing takes of the track's lines (off the screen's thread; the document is not edited)."""
        self.voice.start(track_id)

    def close(self):
        self.voice.close()
