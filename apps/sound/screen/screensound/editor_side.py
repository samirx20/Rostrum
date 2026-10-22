"""Beside the Editor (bottom dock), what the piano roll can't show for the selection's track: a voice track's lines
and Make voice (voice_card.py), a plug-in instrument's settings and its choice. These were on the Instruments
page's cards; with the page gone they follow the track the Editor shows. Exposed to QML as `editorSide`.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot

from .voice_card import VoiceMaker, card_roles


class EditorSide(QObject):
    changed = Signal()
    typingChanged = Signal()

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.bridge, self._typing = bridge, {}
        self.voice = VoiceMaker(bridge, self)
        for s in (self.voice.changed, bridge.timelineChanged, bridge.docChanged):
            s.connect(self.changed)
        bridge.voiceWanted.connect(self.voice.start)
        bridge.side = self                                    # the scripted steps reach it (line-type)
        self.voice.changed.connect(bridge._rebuild)             # a line starts or stops being spoken: its block says so

    def _track(self) -> dict:
        tid = self.bridge.roll.get("id", "")
        return self.bridge.doc.item(tid) if tid and self.bridge.doc.has(tid) else {}

    @Property("QVariantMap", notify=changed)
    def track(self):
        """{id, isPlugin, isVoice, lines, missing, voiceStatus, voiceBusy, voiceFailed} of the Editor's track."""
        t = self._track()
        return {"id": t.get("id", ""), "isPlugin": t.get("instrument") == "plugin",
                **card_roles(t, self.voice.state(t.get("id", "")))}

    # ---- typing a line on the lane (DESIGN.md §3.11 step 2) ---------------------------------------------------
    @Property("QVariantMap", notify=typingChanged)
    def typing(self):
        """{track, t} while a text box is open in a voice track's lane at that time ({} = none)."""
        return self._typing

    @Slot(str, result=bool)
    def isVoiceTrack(self, track_id):
        return self.bridge.doc.has(track_id) and self.bridge.doc.item(track_id).get("instrument") == "voice"

    @Slot(str, float, result=bool)
    def startTyping(self, track_id, t):
        """Double-click on a voice lane, or Add line at playhead: the box opens in the lane at `t`."""
        if not self.isVoiceTrack(track_id):
            return False
        self._typing = {"track": track_id, "t": round(max(0.0, t), 3)}
        self.typingChanged.emit()
        return True

    @Slot()
    def cancelTyping(self):
        if self._typing:
            self._typing = {}
            self.typingChanged.emit()

    @Slot(str, str, result=bool)
    def typeLine(self, track_id, text):
        """Enter in "Type what she says": a line at the playhead (or just after the last line when the playhead is
        before its end), one step, selected; its speech is made at once (DESIGN.md §10 #1: made when you finish
        typing; once, kept)."""
        b = self.bridge
        row = next((r for r in b.tracks if r["id"] == track_id), {"blocks": []})
        ends = [x["t"] + x["dur"] for x in row["blocks"] if x["type"] == "line"]
        return self.typeAt(track_id, text, max(b.time, max(ends) + 0.1) if ends and b.time < max(ends) else b.time)

    @Slot(str, str, float, result=bool)
    def typeAt(self, track_id, text, at):
        """Enter in the lane's box: the line at `at`, then made when typing finishes (also the typing box's end)."""
        b, words = self.bridge, text.strip()
        self.cancelTyping()
        if not words or not b.doc.has(track_id):
            return False
        before = {ln["id"] for ln in b.doc.item(track_id).get("lines", [])}
        if not b._act([{"op": "line.add", "target": [track_id], "args": {"text": words, "at": round(at, 3)}}], "Add line"):
            return False
        new = [ln["id"] for ln in b.doc.item(track_id).get("lines", []) if ln["id"] not in before]
        if new:
            b.select(new[0])
        self.voice.start(track_id)
        return True

    @Slot(str, int, result=bool)
    def stepTake(self, line_id, step):
        """The ◂ ▸ arrows: the line selected, then the earlier / later made take (`line.set {seed}`, one step; instant,
        the audio is in the cache)."""
        self.bridge.select(line_id)
        return bool(self.bridge.run("take_next" if step > 0 else "take_prev"))

    @Slot(str)
    def makeVoice(self, track_id):
        """Make the missing takes of the track's lines (off the screen's thread; the document is not edited)."""
        self.voice.start(track_id)

    def close(self):
        self.voice.close()
