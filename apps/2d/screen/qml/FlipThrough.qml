import QtQuick

// Hold , or . on a frame-by-frame layer to flip through its drawings at the scene's speed (UX_SPEC §3.9 Flip
// through); a tap steps one drawing. Keys give no release, so a held key is told by its auto-repeat: a press is a
// repeat only when it follows the last one within 100 ms (the repeat rate) AND the key has been down for 350 ms
// (the wait before repeating), so taps, however quick, step once each. The first press steps once; when repeats stop
// (the key is up) the flipping stops. Each drawing shows for as long as it is held (painter.flipFrame), round from the
// last to the first. Only the playhead moves: no change.
Item {
    id: flip
    property int dir: 0
    property real first: 0          // when this run of presses began, and the latest press (ms)
    property real last: 0
    property bool holding: false
    readonly property real frameMs: 1000 / (backend.frameInfo.fps || 30)
    function press(d) {
        const now = Date.now()
        if (up.running && d === dir) {
            const repeat = now - last < 100 && (holding || now - first >= 350)
            last = now
            if (repeat) { holding = true; up.interval = 140; up.restart(); if (!run.running) run.go(); return }   // held
            if (!holding) { painter.goFrame(d); up.interval = 700; up.restart(); return }                       // a quick tap: one step
        }
        run.stop(); dir = d; holding = false; first = last = now; painter.goFrame(d)
        up.interval = 700; up.restart()            // longer than the keyboard's wait before it repeats
    }
    Timer { id: up; onTriggered: { run.stop(); flip.holding = false } }      // no repeat came in time: the key is up
    Timer {
        id: run
        repeat: false
        function go() { const held = painter.flipFrame(flip.dir); if (held > 0) { interval = held * flip.frameMs; start() } }
        onTriggered: if (up.running) go()
    }
}
