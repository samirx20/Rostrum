"""+ Add › From a file… (Ctrl+I): a file brought into the song by what it is, each as one change (one undo step):

- a sound file (WAV, MP3, FLAC, OGG, AIFF, M4A) -> a new track holding it as a clip at the playhead (`track.add` +
  `clip.add`); the file is copied into the song's `media/` folder first, so the song carries it;
- a MIDI file (.mid) -> its tracks with their notes and drum hits, markers and sections (rostrum_sound.midi's
  `import_calls`, what an agent's import is); its tempo map and key replace the song's only while the song has no
  tracks yet, so a song already written is never re-timed;
- a video -> the picture to work to (`doc.set picture`, as + Add › Picture…).

Anything else is refused in one sentence. Exposed to QML as `fileIn`.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Property, QObject, QUrl, Slot
from rostrum_core import ids
from rostrum_core.tree import index
from rostrum_sound import midi
from rostrum_sound.doc import media as media_
from rostrum_sound.doc.registry import LISTS

SOUNDS = {".wav", ".mp3", ".flac", ".ogg", ".aif", ".aiff", ".m4a"}
MIDI = {".mid", ".midi"}
VIDEOS = {".mp4", ".mov", ".webm", ".mkv", ".avi"}
FILTERS = ["Sounds, MIDI and videos (" + " ".join("*" + e for e in sorted(SOUNDS | MIDI | VIDEOS)) + ")"]


def sound_calls(root: dict, path: Path, at: float, media: str | None = None) -> tuple[list[dict], str]:
    """A new track named after the file, with the file as one clip at `at` seconds: (calls, the new track's id)."""
    tid = ids.counted(set(index(root, LISTS)), "audio")
    return ([{"op": "track.add", "args": {"id": tid, "name": path.stem, "instrument": "none"}},
             {"op": "clip.add", "target": [tid], "args": {"media": media or str(path), "at": round(at, 4)}}], tid)


class FileIn(QObject):
    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.bridge = bridge

    @Property("QStringList", constant=True)
    def filters(self):
        return FILTERS

    @Slot(str, result=bool)
    def add(self, chosen):
        b = self.bridge
        path = Path(QUrl(chosen).toLocalFile() if chosen.startswith("file:") else chosen)
        kind = path.suffix.lower()
        if not path.is_file():
            b._fail(f"Error: add from a file: {path} is not there.")
            return False
        if kind in VIDEOS:
            b.setPicture(str(path))
            return True
        if kind not in SOUNDS | MIDI:
            b._fail(f"Error: add from a file: {path.name} is not a sound, a MIDI file or a video Sound can use.")
            return False

        def go():
            root = b.doc.data
            before = {t["id"] for t in root.get("tracks", [])}
            if kind in SOUNDS:
                calls, _ = sound_calls(root, path, b.time, media_.keep(b.doc.folder, path))   # copied into the song
                b._apply(calls, f"Add {path.name}")
            else:
                calls, skipped = midi.import_calls(root, path, song_map=not before)
                b._apply(calls, f"Add {path.name}")
                if skipped:
                    b.say(f"Added {path.name}; left out: {'; '.join(skipped)}")
            new = [t["id"] for t in b.doc.data.get("tracks", []) if t["id"] not in before]
            if new:
                b.select(new[0])
        return b._guard(go)
