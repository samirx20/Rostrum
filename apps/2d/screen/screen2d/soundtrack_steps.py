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
    sound cue [words…]          Add a sound here… on the selected layer: the picker, searched for the words
    sound cue pick <n>          tie the picker's n-th sound (1 = the first) to the layer; prints the cue and its marker
    sound cue twice <a> <b>     two searches typed fast (b before a's answer): the list must be b's, never a's
    sound video [<layer> on|off]  print the Video sound rows; with a layer: its row's 🔊 (mute on / off)
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
    elif what == "cue" and rest[1:2] == ["pick"]:
        cp = bridge.cuePick
        row = cp.sounds[int(rest[2]) - 1]
        if not cp.pick(row["path"]):
            raise RuntimeError(f"step {step!r}: the cue was refused (the status line says why)")
        _pump(0.2)
        print("cue:", row["about"], "| markers:", [(m["name"], m["at"]) for m in __import__("rostrum_core").markers.listing(bridge.doc.folder)])
    elif what == "cue" and rest[1:2] == ["twice"]:
        cp = bridge.cuePick
        if not cp.start():
            raise RuntimeError(f"step {step!r}: Add a sound here needs one layer selected")
        cp.search(rest[2])
        cp.search(rest[3])                          # at once: a's answer may still be on its way
        if not cp.wait(30):
            raise RuntimeError(f"step {step!r}: the sound search took over 30 s")
        _pump(0.5)                                  # a late answer for a must not replace b's list
        from rostrum2d import sound_cues
        want = [r["path"] for r in sound_cues.choices(rest[3], 40)]
        got = [r["path"] for r in cp.sounds]
        if got != want or cp.words != rest[3]:
            raise RuntimeError(f"step {step!r}: the list is not {rest[3]!r}'s ({len(got)} shown, {len(want)} expected)")
        print(f"sounds for {rest[3]!r} (after {rest[2]!r}):", len(got))
    elif what == "cue":
        cp = bridge.cuePick
        cp.search(" ".join(rest[1:]))
        if not cp.start():
            raise RuntimeError(f"step {step!r}: Add a sound here needs one layer selected")
        if not cp.wait(30):                         # the search runs off the screen's thread (sound_cue_pick.py)
            raise RuntimeError(f"step {step!r}: the sound search took over 30 s")
        _pump(0.3)
        print("sounds:", len(cp.sounds))
    elif what == "video":
        vs = st.videos
        if len(rest) > 2 and not vs.setMuted(rest[1], rest[2] == "on"):
            raise RuntimeError(f"step {step!r}: the mute was refused (the status line says why)")
        _settle(bridge)
        for _ in range(100):                        # the waveform is read off the screen's thread
            if all(r["peaks"] or r["problem"] for r in vs.rows.values()):
                break
            _pump(0.05)
        print("video sound:", {k: {**v, "peaks": len(v["peaks"])} for k, v in vs.rows.items()})
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
