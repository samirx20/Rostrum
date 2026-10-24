"""The timeline's Video sound rows (UX_SPEC 3.28 Sync sound): under each video layer whose file has sound, a sub-row with
that sound's waveform, drawn along the layer's bar (it moves and trims with the bar, live while dragging: the row reads
the bar's own times). RostrumSound mixes it (rostrum2d/sync_sound.py puts it in the song); the row only shows it, and
its mute is Sound's operation on that clip (`clip.set {volume}` in the song: one change, in 2D's one Undo, the same
operation agents call through Sound's tools). Offered to QML as `backend.soundtrack.videos`.

    rows: {layer id: {pieces, speed, muted, peaks, rate, problem}}   # peaks of the video's own sound, file seconds
    pieces: [{from, in, length}]: what Sound plays, `from` seconds after the bar's start (sync_sound.wanted: a loop's
    time rounds, cut to its groups, silent once the file ends); the row draws only those.
The waveform is read once per file off the screen's thread (video_audio.wav, waveform.measure).
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum2d import project_sound, sound_cues, sync_sound, video_audio
from rostrum_gui.frames import PictureWorker

from . import waveform

NO_SONG = "Sound mixes it once the project has a RostrumSound item"


class _Read(PictureWorker):
    read = Signal(str, "QVariantMap")

    def open_engine(self):
        return None                 # ffmpeg and a WAV read: no engine

    def handle(self, eng, file):
        w = waveform.measure(video_audio.wav(Path(file)))
        self.read.emit(file, {"peaks": w["peaks"], "rate": w["rate"]})

    def describe(self, file, error):
        return f"Error: the sound of {Path(file).name}: {error}"


class VideoSound(QObject):
    changed = Signal()

    def __init__(self, soundtrack, bridge):
        super().__init__(soundtrack)
        self.st, self.b, self._rows, self._waves, self._asked = soundtrack, bridge, {}, {}, set()
        self._reader = _Read("video-sound", self)
        self._reader.read.connect(self._take)
        self._reader.failed.connect(self.b._fail)
        self._reader.start()
        self._unsub = bridge.doc.subscribe(self._on_doc)
        self.refresh()

    rows = Property("QVariantMap", lambda self: self._rows, notify=changed)

    def _on_doc(self, ev):
        """A drag's step: the bar leads (nothing here). A change that can't move a video's sound (a look edit, a key,
        a stroke: sound_cues.moves_sound) leaves the rows as they are."""
        if ev.kind == "reset" or ev.kind == "change" and sound_cues.moves_sound(ev.change):
            self.refresh()

    def refresh(self):
        """The rows from the document's video layers and the song's clips (each layer's sound: muted or not)."""
        folder = self.b.doc.folder
        try:
            want = sync_sound.wanted(folder, self.b.doc) if folder and self.b.doc.item_id else {}
            clips = self._clips(folder) if want else None
        except Exception as e:  # noqa: BLE001  said, never an empty timeline passed off as "no sound"
            return self.b._fail_error(e, f"Error: video sound: {e}")
        rows = {}
        for lid, w in want.items():
            c = (clips or {}).get(sync_sound.clip_id(self.b.doc.item_id, lid))
            wave = self._waves.get(w["file"], {})
            if w["file"] not in self._waves and w["file"] not in self._asked:
                self._asked.add(w["file"])
                self._reader.post_ordered(w["file"])
            speed = float(self.b.doc.item(lid).get("speed", 1.0)) or 1.0
            heard = [{"from": round(w["at"] + q["after"] - w["start"], 6), "in": q["in"], "length": q["length"]}
                     for q in w["pieces"]]
            rows[lid] = {"pieces": heard, "speed": speed,
                         "muted": bool(c is not None and float(c.get("volume", 1.0)) == 0.0),
                         "peaks": wave.get("peaks", []), "rate": wave.get("rate", 100.0),
                         "problem": "" if clips is not None else NO_SONG}
        if rows != self._rows:
            self._rows = rows
            self.changed.emit()

    def _clips(self, folder) -> dict | None:
        song = project_sound.song(folder, self.b.comp().get("soundtrack", ""))
        if song is None:
            return None
        snd = project_sound.open_song(folder, song["id"])
        return {c["id"]: c for t in snd.data.get("tracks", []) if t["id"] == sync_sound.TRACK for c in t.get("clips", [])}

    def _take(self, file, wave):
        self._waves[file] = dict(wave)
        self.refresh()

    @Slot(str, bool, result=bool)
    def setMuted(self, layer, on):
        """The row's 🔊: its clips' volume in Sound's song to 0 (muted) or 1, as the person's one change."""
        folder = self.b.doc.folder
        try:
            song = project_sound.song(folder, self.b.comp().get("soundtrack", ""))
            if song is None:
                raise RuntimeError(NO_SONG)
            snd = project_sound.open_song(folder, song["id"])
            name = self.b.label_of(self.b.doc.item(layer))
            ids = sync_sound.layer_clips(snd, self.b.doc.item_id or "", layer)     # a looped video: every time round
            snd.apply([{"op": "clip.set", "target": ids, "args": {"volume": 0.0 if on else 1.0}}], self.b.who,
                      label=f"{'Mute' if on else 'Unmute'} the sound of {name}")
        except Exception as e:  # noqa: BLE001  loud, in words
            self.b._fail_error(e, f"Error: video sound: {e}")
            return False
        self.st.check()
        self.refresh()
        return True

    def close(self):
        self._unsub()
        self._reader.close()
