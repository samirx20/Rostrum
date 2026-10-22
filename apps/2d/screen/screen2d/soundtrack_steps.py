"""Scripted steps for the project's sound (backend.soundtrack, soundtrack.py), through the same calls the screen makes.

    sound wait                  wait for the mix (the render, the peaks, the grid) and print what plays
    sound mute on|off           the 🔊 button              sound beats on|off   the ruler's ▾ › Show beats
    sound beat prev|next        Shift+, / Shift+.         sound scrub <s>      the playhead dragged there (a burst)
    sound play <s> [hold]       play for that long, print where the speaker and the picture are (hold: keep playing)
    sound wav <path>            copy the mix 2D plays to a WAV (to listen to / measure)
    sound pick <item|->         Scene settings › Soundtrack (comp.set {soundtrack}; - = the project's sound)
    sound menu                  the Sound row's right-click     sound open [dry]   Open in RostrumSound (dry: print it)
    sound problem <png>         the mix must have failed (no engine …): a picture of the screen saying so, then the
                                status line is cleared so the walk goes on
    rulermenu                   the ruler's ▾ menu
"""
from __future__ import annotations

import shutil
import time

from PySide6.QtCore import QCoreApplication, QMetaObject, QObject

WORDS = ("sound", "rulermenu")


def _settle(bridge, seconds=60.0):
    st = bridge.soundtrack
    st.check()
    end = time.time() + seconds
    while (st.busy() or (st.present and not st.seconds and not st.problem)) and time.time() < end:
        QCoreApplication.processEvents()
        time.sleep(0.02)
    for _ in range(5):
        QCoreApplication.processEvents()
    if st.busy():
        raise RuntimeError(f"the soundtrack's render did not finish in {seconds:.0f} s")


def _pump(seconds):
    end = time.perf_counter() + seconds
    while time.perf_counter() < end:
        QCoreApplication.processEvents()
        time.sleep(0.005)


def _invoke(win, name, fn):
    found = win.findChild(QObject, name)
    if found is None:
        raise RuntimeError(f"no {name!r} on screen")
    QMetaObject.invokeMethod(found, fn)
    QCoreApplication.processEvents()


def do_sound_step(bridge, win, word, rest, step):
    st = bridge.soundtrack
    if word == "rulermenu":
        return _invoke(win, "timeRuler", "openViewMenu")
    what = rest[0] if rest else "wait"
    if what == "wait":
        _settle(bridge)
        print("soundtrack:", st.describe() or "none (the project has no sound)")
    elif what == "mute":
        st.setMuted(rest[1] == "on")
    elif what == "beats":
        _settle(bridge)
        st.setShowBeats(rest[1] == "on")
    elif what == "beat":
        if not st.stepBeat(-1 if rest[1] == "prev" else 1):
            raise RuntimeError(f"step {step!r}: no beat that way")
        print(f"playhead on the beat at {bridge.time:.3f} s")
    elif what == "scrub":
        bridge.setTime(float(rest[1]))
        st.scrub(float(rest[1]))
        _pump(0.3)
    elif what == "play":
        _settle(bridge)
        bridge.togglePlay()
        _pump(float(rest[1]))
        heard = st.heard()
        print(f"after {rest[1]} s: picture at {bridge.time:.3f} s, speaker at "
              f"{'-' if heard is None else f'{heard:.3f} s'}; player alive: {st._play.alive()}")
        if "hold" not in rest[2:]:               # `hold`: still playing (a picture while it plays)
            bridge.togglePlay()
    elif what == "wav":
        _settle(bridge)
        if not st.describe().get("file"):
            raise RuntimeError(f"step {step!r}: no mix ({st.problem or 'the project has no sound'})")
        shutil.copyfile(st.describe()["file"], rest[1])
        print("mix copied to", rest[1])
    elif what == "pick":
        item = "" if rest[1] == "-" else rest[1]
        bridge.doc.apply([{"op": "comp.set", "target": [bridge.comp_id], "args": {"soundtrack": item}}], bridge.who)
        _settle(bridge)
        print("soundtrack:", st.describe() or "none")
    elif what == "menu":
        _invoke(win, "soundRow", "openMenu")
    elif what == "open":
        if "dry" in rest:
            print("would run:", " ".join(st.open_command()))
        else:
            st.openInSound()
    elif what == "problem":
        _settle(bridge)
        if not st.problem:
            raise RuntimeError(f"step {step!r}: expected the soundtrack to say what failed; it rendered")
        _pump(0.8)
        if not win.grabWindow().save(rest[1]):
            raise RuntimeError(f"could not save {rest[1]}")
        print("said:", st.problem)
        bridge._set_status("")
    else:
        raise ValueError(f"unknown step {step!r}")


SONG = '''tempo(120); beats_per_bar(4); length(bar(3))
d = track("drums", kit="synth")
for b in range(8):
    d.hit("kick", at=beat(b))
d.hit("cymbal", at="#drop")
'''
FILM = '''comp("main", width=1280, height=720, fps=30, duration=4)
text("title", body="Drop", x=640, y=200, end=1.4)
shape("logo", x=640, y=360, start=0.5, end=3.0)
'''


def sound_project(folder) -> list[str]:
    """Start args for a project with sound (the layout check's Sound states): a short song with a tempo and the
    shared marker "drop" at 2 s, and a scene "film" (item) with two layers."""
    from pathlib import Path

    from rostrum_core import Document, Who, markers
    from rostrum_core.storage import save
    from rostrum_sound import KIND, run_source
    from rostrum_sound.doc import markers as sound_markers
    folder = Path(folder)
    (folder / "docs").mkdir(parents=True, exist_ok=True)
    markers.edit(folder, [{"op": "marker.add", "args": {"name": "drop", "at": 2.0}}], Who.agent("layout"))
    with sound_markers.project(folder):
        song = Document.new(KIND, folder, "song")
        song.run_script("song.py", run_source(SONG, "song.py"), Who.agent("layout"))
        save(song)
    script = folder.parent / f"{folder.name}-film.py"
    script.write_text(FILM, encoding="utf-8")
    return ["--doc", str(folder), "film", "--script", str(script)]
