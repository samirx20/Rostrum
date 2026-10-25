import QtQuick
import "Blocks.js" as Blocks

// A painted surface over a time ruler (an arrangement row's blocks and grid, the roll's notes and velocities) that
// keeps its picture through a change of its width: the Library or a panel opening, the window resized. Its backing
// picture is as wide as the screen, so a narrower or wider row never makes it again; a resize that moves the
// ruler's scale or start (a song shown whole is fitted to the new width) shows the picture it has, stretched to the
// new view at once, and paints it whole `slot` frames later (rows take turns, so no frame paints every row). A zoom
// or a scroll at the same width paints at once, as before. Painting every row whole on a Library click cost
// 30-60 ms on a 3-minute song.
//
// The surface paints as a Canvas does, with two duties: `wholeWanted` is its "paint everything again", and its
// whole paint calls `markPainted()` (the view it now shows) and skips while `waiting` (the stretched picture stands).
// A surface painted in parts (Blocks.js) keeps what its picture shows in `kept` and asks for a whole paint with
// `again()` (`whole`); once idle after one, the picture's columns are made (Blocks.index), so the first edit after
// never pays for them.
Canvas {
    id: v
    property var ruler                          // start (s) and perSec (px per s) of what is shown
    property int slot: 0                        // the frame after a resize it paints again in
    signal wholeWanted()
    readonly property var kept: Blocks.kept()  // what the picture shows (painting in parts)
    property bool whole: true
    function again() { whole = true; requestPaint() }
    onPainted: if (!kept.whole && kept.cols === null) idle.restart()
    Timer { id: idle; interval: 150; onTriggered: if (!v.whole) Blocks.index(v.kept) }
    readonly property bool waiting: later.running
    property real paintedStart: 0               // the view the picture was painted at
    property real paintedPerSec: 0
    property real paintedWidth: -1              // the width it was painted for
    width: Math.max(parent ? parent.width : 0, Screen.width)
    transform: [
        Scale { xScale: v.paintedPerSec > 0 ? v.ruler.perSec / v.paintedPerSec : 1 },
        Translate { x: v.paintedPerSec > 0 ? (v.paintedStart - v.ruler.start) * v.ruler.perSec : 0 }
    ]

    function markPainted() {
        paintedStart = ruler.start; paintedPerSec = ruler.perSec; paintedWidth = parent ? parent.width : 0
    }
    function viewMoved() {
        if (later.running || (parent && Math.abs(parent.width - paintedWidth) > 0.5 && paintedWidth >= 0)) later.restart()
        else wholeWanted()
    }
    Connections { target: v.parent; function onWidthChanged() { v.viewMoved() } }
    Connections { target: v.ruler; function onStartChanged() { v.viewMoved() } function onPerSecChanged() { v.viewMoved() } }
    Timer { id: later; interval: 40 + 16 * (v.slot % 6); onTriggered: v.wholeWanted() }
}
