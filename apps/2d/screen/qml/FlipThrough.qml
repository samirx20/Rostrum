import QtQuick

// Hold , or . on a frame-by-frame layer to flip through its drawings at the scene's speed (UX_SPEC §3.9 Flip
// through); a tap steps one drawing. Keys give no release, so a held key is its auto-repeat: the first press steps
// once, a repeat starts the flipping, and when the repeats stop (the key is up) the flipping stops. Each drawing shows
// for as long as it is held (painter.flipFrame), round from the last to the first. Only the playhead moves: no change.
Item {
    id: flip
    property int dir: 0
    readonly property real frameMs: 1000 / (backend.frameInfo.fps || 30)
    function press(d) {
        if (up.running && d === dir) { up.interval = 140; up.restart(); if (!run.running) run.go(); return }   // held
        run.stop(); dir = d; painter.goFrame(d)
        up.interval = 700; up.restart()            // longer than the keyboard's wait before it repeats
    }
    Timer { id: up; onTriggered: run.stop() }      // no repeat came in time: the key is up
    Timer {
        id: run
        repeat: false
        function go() { const held = painter.flipFrame(flip.dir); if (held > 0) { interval = held * flip.frameMs; start() } }
        onTriggered: if (up.running) go()
    }
}
