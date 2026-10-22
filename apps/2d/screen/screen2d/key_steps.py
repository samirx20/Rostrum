"""Scripted steps for keys in the timeline, the key bar, K, Stagger and , / . (steps.py hands these over). The same
calls a click, a drag or a key makes.

    keypick <key id>[,<key id>…] [ctrl|shift]   click a diamond (the ids it stands for); Ctrl adds / removes, Shift the run
    keybox <id>[,<id>…] [<id>…] [ctrl|shift]     a box dragged over diamonds (each argument one diamond's ids)
    keybox time <t0> <t1> [ctrl|shift]           a box over every open row's diamonds between those times
    keydrag2 <key id> <from s> <to s> [snap] [hold]   press a picked key at <from>, let go at <to> (composition seconds): all
                                                 move; `snap`: within 0.1 s it snaps (time_snap.py); `hold`: not let go yet
    keystretch <key id> <from s> <to s> [snap] [hold] Alt+drag the first or last picked key: the picked keys stretch in time
    keyafter <stay|repeat|pingpong|carry>        the key bar's ⋯ › After the last key
    easeplay on|off                              the key bar's ⋯ › Play the ease when picked
    wait <ms>                                    let the screen run that long (an ease playing once)
    keymore                                      open the key bar's ⋯
    keydelete                                    Delete with keys picked
    showanim                                     A: the selection's animated settings only; again folds them
    ease <linear|easeIn|easeOut|smooth|spring|hold|custom>   the key bar's Ease ▾ (or a key's right-click)
    easekey <smooth|ease_in|ease_out|jump>       F9 / Shift+F9 / Ctrl+Shift+F9 / Ctrl+Alt+J
    easecurve <x1> <y1> <x2> <y2>                drag the small curve's handles there (one change)
    spring <bounce> <speed>                      drag the Bounce / Speed sliders there (one change)
    keytime <s> | keyvalue <v>                   one key's Time / Value fields
    easemenu                                     a key's right-click: the Ease list opens
    keyhere                                      K: key the selected layers here
    keycopy | keypaste                           Ctrl+C / Ctrl+V (keys picked: keys; keys copied + layers selected: paste)
    stagger <frames> [order] [open]              Stagger… on the selection, that amount and order; kept unless "open"
    event prev|next                              , / . : the playhead to the previous / next thing that happens
"""
from __future__ import annotations

WORDS = ("keypick", "keybox", "keydrag2", "keystretch", "keydelete", "showanim", "ease", "easekey", "easecurve", "spring",
         "keytime", "keyvalue", "easemenu", "keyhere", "keycopy", "keypaste", "stagger", "event", "keyafter",
         "easeplay", "wait", "keymore")
HOW = ("ctrl", "shift")


def _row_of(bridge, key_id):
    for row in bridge.layers:
        groups = [k.get("ids", [k["id"]]) for k in row["keys"]]
        if any(key_id in g for g in groups):
            return groups
    return [[key_id]]


def _bar_steps(bridge, word, rest, step):
    kb = bridge.keyBar
    if word == "ease":
        ok = kb.setEase(rest[0])
    elif word == "easecurve":
        ok = kb.begin("curve")
        kb.curveTo(*(float(r) for r in rest[:4]))
        kb.end()
    elif word == "spring":
        ok = kb.begin("spring")
        kb.springTo(float(rest[0]), float(rest[1]))
        kb.end()
    elif word == "keytime":
        ok = kb.setTime(float(rest[0]))
    elif word == "keyvalue":
        ok = kb.setValue(float(rest[0]))
    else:                                           # easemenu
        kb.askMenu(700.0, 760.0)
        ok = True
    if not ok:
        raise RuntimeError(f"step {step!r}: the key bar refused (no keys picked?) {bridge.status}")
    print("keybar", kb.ease, kb.handles, kb.feel)


def do_key_step(bridge, word, rest, step):
    keys = bridge._keys
    if word == "keypick":
        ids = rest[0].split(",")
        keys.click(ids, rest[1] if rest[1:] else "", _row_of(bridge, ids[0]))
        print("keys", keys.ids)
    elif word == "keybox":
        how = rest[-1] if rest[-1] in HOW else ""
        args = [r for r in rest if r not in HOW]
        if args[0] == "time":                       # a box over every row's diamonds from t0 to t1 (seconds, as shown)
            t0, t1 = float(args[1]), float(args[2])
            groups = [k.get("ids", [k["id"]]) for row in bridge.layers for k in row["keys"] if t0 - 1e-6 <= k["t"] <= t1 + 1e-6]
        else:
            groups = [r.split(",") for r in args]
        keys.box(groups, how)
        print("keys", keys.ids)
    elif word in ("keydrag2", "keystretch"):
        begin = keys.beginDrag if word == "keydrag2" else keys.beginStretch
        if not begin(rest[0], float(rest[1])):
            raise RuntimeError(f"step {step!r}: {rest[0]} is not a picked key (or not the first / last, to stretch)")
        t0, t1 = float(rest[1]), float(rest[2])
        for f in (0.5, 1.0):                         # as a hand pulls it
            keys.dragTo(t0 + (t1 - t0) * f, 0.1 if "snap" in rest else 0.0)
        if "hold" not in rest:
            keys.endDrag()
        print("drag label", ascii(bridge.timeSnap.text))
    elif word == "keyafter":
        if not bridge.keyBar.setAfter(rest[0]):
            raise RuntimeError(f"step {step!r}: no last key picked ({bridge.status})")
    elif word == "keymore":
        from PySide6.QtCore import QMetaObject, QObject
        from PySide6.QtGui import QGuiApplication
        more = next(w.findChild(QObject, "keyMore") for w in QGuiApplication.topLevelWindows() if w.findChild(QObject, "keyMore"))
        QMetaObject.invokeMethod(more, "clicked")
    elif word == "easeplay":
        bridge.easePlay.setOn(rest[0] == "on")
    elif word == "wait":
        import time
        from PySide6.QtCore import QCoreApplication
        end = time.perf_counter() + float(rest[0]) / 1000
        while time.perf_counter() < end:
            QCoreApplication.processEvents()
        print("time", bridge.time, "playing", bridge.playing)
    elif word in ("ease", "easecurve", "spring", "keytime", "keyvalue", "easemenu"):
        _bar_steps(bridge, word, rest, step)
    elif word in ("easekey", "keyhere", "keycopy", "keypaste", "keydelete"):
        job = {"keyhere": "key_here", "keycopy": "copy", "keypaste": "paste", "keydelete": "delete"}.get(word) or rest[0]
        if not bridge.layerCommand(job):
            raise RuntimeError(f"step {step!r}: nothing ran ({bridge.status})")
        print("status", bridge.status)
    elif word == "stagger":
        st = bridge.stagger
        if not st.start():
            raise RuntimeError(f"step {step!r}: {bridge.status}")
        st.setBy(int(rest[0]))
        if rest[1:] and rest[1] != "open":
            st.setOrder(rest[1])
        if "open" not in rest:
            st.end()
    elif word == "event":
        bridge.stepEvent(-1 if rest[0] == "prev" else 1)
        print("time", bridge.time)
    elif word == "showanim":
        bridge.showAnimated()
        print("rows", [r["label"] for r in bridge.layers])
