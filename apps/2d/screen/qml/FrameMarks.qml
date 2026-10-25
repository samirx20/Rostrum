import QtQuick
import RostrumKit

// Frame-by-frame on a timeline track: each drawing a cell as wide as it is held (`frames` from the layer's row:
// {id, n, at, held, t0, t1}), centred in the row like a layer's bar, two shades so neighbours read apart. The drawing
// at the playhead is lit (the accent, as a selected bar); the ones the onion skin shows have a red (before) or green
// (after) line under their cell. Sits in a track whose x is the ruler's x - 8, like the key diamonds.
// Click a cell: the playhead goes to it (it is the drawing painted into). Drag it: it moves to another frame (Alt: a
// copy goes there). Drag its right edge (a cell wide enough to grab it): it is held longer or shorter. Right-click: Delete. Each is one change (painter).
// The layer's key diamonds lie over the cells (barless, LayerTrack.qml): every click area here steps around them (`free`),
// and one with under 16 px left has none (zoom in), so a cell and a key never take the same click at any zoom.
Item {
    id: m
    property var frames: []
    property var again: []
    property var timeRuler
    property string owner: ""
    readonly property real fps: backend.frameInfo.fps || 30
    readonly property int cur: { for (const f of frames) if (backend.time >= f.t0 - 1e-6 && backend.time < f.t1 - 1e-6) return f.n; return 0 }
    readonly property bool onion: painter.onionOn && painter.drawingId === owner
    function framesOf(dx) { return Math.round(dx / m.timeRuler.perSec * m.fps) }
    property bool trims: false            // the layer's ends can be dragged here (a layer with a start and an end)
    property real layerStart: 0
    property real layerEnd: 1e9
    property bool drawing: false          // a drawing layer's row (its frames may be none yet)
    property var keys: []                 // the row's keys ({t}): each diamond's 16 px, centred on its time
    function keyX(k) { return 8 + Math.round(m.timeRuler.xOf(k.t)) }
    // The widest stretch of [x0, x1] no diamond covers, as [a, b]; null when under 16 px is left.
    function free(x0, x1) {
        let best = null, a = x0
        const cuts = m.keys.map(k => m.keyX(k)).filter(c => c + 8 > x0 && c - 8 < x1).sort((p, q) => p - q)
        for (const c of [...cuts, x1 + 8]) {
            const b = Math.min(x1, c - 8)
            if (b - a >= 16 && (!best || b - a > best[1] - best[0])) best = [a, b]
            a = Math.max(a, c + 8)
        }
        return best
    }
    // The empty frames before the first drawing (or all of them, with none): a faint "+" on each, or (frames under
    // 16 px wide) one "+" over the whole empty stretch. One click there only picks the layer and moves the playhead
    // (never makes anything); a DOUBLE-click, inside the layer's own time (`layerStart`..`layerEnd`), is a new drawing on
    // the frame under the pointer (painter.newFrame on an empty frame puts it at the playhead).
    readonly property real step: m.timeRuler.perSec / m.fps
    readonly property bool wide: step >= 16
    readonly property int from: Math.round(Math.max(0, layerStart) * m.fps)          // the layer's own time starts here
    readonly property int to: !drawing ? 0 : frames.length ? Math.round(frames[0].t0 * m.fps)
                              : Math.round(Math.min(layerEnd, backend.frameInfo.duration || 0) * m.fps)
    readonly property int empty: Math.max(0, to - from)
    // Every list below is a KeptRepeater (index-based, delegates kept): a Repeater over the list itself remade every
    // cell, with its menu and tips, at each change of the row, so each new drawing cost more than the one before.
    KeptRepeater {
        id: emptyCells
        needed: m.empty === 0 ? 0 : m.wide ? m.empty : 1
        delegate: Text {
            required property int index
            objectName: "emptyFrame" + index
            visible: index < emptyCells.needed && x + width > 0 && x < m.width && m.free(x, x + width) !== null
            x: 8 + Math.round(m.timeRuler.xOf((m.from + index) / m.fps)); height: m.height
            width: m.wide ? Math.floor(m.step) : Math.max(16, Math.round(m.timeRuler.xOf(m.to / m.fps) - m.timeRuler.xOf(m.from / m.fps)) - 1)
            horizontalAlignment: m.wide ? Text.AlignHCenter : Text.AlignLeft; leftPadding: m.wide ? 0 : 4
            verticalAlignment: Text.AlignVCenter
            text: "+"; color: Theme.fg3; opacity: plus.containsMouse ? 0.9 : 0.35
            font.family: uiFont; font.pixelSize: Theme.label
            MouseArea { id: plus; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        HoverTip { hovered: plus.containsMouse; text: "Double-click: new drawing here" }
                        function frameAt(ev) { return m.from + (m.wide ? parent.index : Math.min(m.empty - 1, Math.floor(ev.x / m.step))) }
                        onClicked: (ev) => { if (backend.selected !== m.owner) backend.select(m.owner)
                                             painter.goToFrame(frameAt(ev)) }
                        onDoubleClicked: (ev) => { if (backend.selected !== m.owner) backend.select(m.owner)
                                                   painter.goToFrame(frameAt(ev)); painter.newFrame(false) } }
        }
    }
    KeptRepeater {  // a looping drawing's later rounds: the same cells again, faint, not to be clicked
        id: againCells
        needed: m.again.length
        delegate: Rectangle {
            required property int index
            readonly property var modelData: m.again[index] || ({ t0: 0, t1: 0, n: 0 })
            visible: index < againCells.needed
            objectName: "againCell"
            x: 8 + Math.round(m.timeRuler.xOf(modelData.t0)); width: Math.max(3, Math.round(m.timeRuler.xOf(modelData.t1) - m.timeRuler.xOf(modelData.t0)) - 1)
            height: 16; y: Math.round((m.height - height) / 2); radius: 3
            color: modelData.n % 2 ? Theme.raised : Theme.hover; opacity: 0.45
            Text { visible: parent.width >= implicitWidth + 10; x: 5; anchors.verticalCenter: parent.verticalCenter; text: modelData.n; color: Theme.fg3
                   font.family: uiFont; font.pixelSize: Theme.label; font.features: { "tnum": 1 } }
        }
    }
    KeptRepeater {
        id: cells
        needed: m.frames.length
        delegate: Item {
            id: f
            required property int index
            readonly property var cellData: m.frames[index] || ({ id: "", n: -1, at: 0, held: 1, t0: 0, t1: 0 })
            // read into plain values: a value that stays the same tells nothing, so a new drawing redoes only the
            // cells that changed (every cell re-measured and re-placed itself at each change: ~3 ms a cell)
            readonly property string fid: cellData.id
            readonly property int n: cellData.n
            readonly property int at: cellData.at
            readonly property int held: cellData.held
            readonly property real t0: cellData.t0
            readonly property real t1: cellData.t1
            visible: index < cells.needed
            readonly property bool current: f.n === m.cur
            readonly property int side: !m.onion || m.cur === 0 ? 0
                : f.n < m.cur && m.cur - f.n <= painter.onionReach.before ? -1
                : f.n > m.cur && f.n - m.cur <= painter.onionReach.after ? 1 : 0
            readonly property bool last: index === m.frames.length - 1
            readonly property real x0: 8 + Math.round(m.timeRuler.xOf(f.t0))      // where it lies, not dragged
            readonly property real w0: Math.max(3, Math.round(m.timeRuler.xOf(f.t1) - m.timeRuler.xOf(f.t0)) - 1)
            readonly property bool grip: !last && w0 >= 32 && m.free(x0 + w0 - 16, x0 + w0) !== null
            readonly property var span: m.free(x0, x0 + Math.max(16, w0 - (grip ? 16 : 0)))   // its click area, clear of keys
            readonly property bool shows: numberWidth.advanceWidth + 10 <= w0 + edge.dx
            TextMetrics { id: numberWidth; font.family: uiFont; font.pixelSize: Theme.label; text: String(f.n) }
            x: x0 + (area.moving ? area.dx : 0)
            width: w0 + edge.dx
            height: m.height
            z: area.moving || edge.pressed ? 2 : 0
            Rectangle {     // the cell: the bar's height and roundness, centred
                id: cell
                objectName: "drawingCell" + f.n
                width: parent.width; height: 16; y: Math.round((parent.height - height) / 2); radius: 3
                color: f.current ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.30)
                     : f.n % 2 ? Theme.raised : Theme.hover
                border.width: f.current ? 1 : 0; border.color: Theme.accent
                opacity: area.moving && area.copying ? 0.6 : 1
                Text {      // the number, only where the whole of it fits (else its hover help says it)
                    id: num
                    visible: f.shows
                    x: 5; anchors.verticalCenter: parent.verticalCenter
                    text: f.n; color: f.current ? Theme.fg : Theme.fg2; font.family: uiFont
                    font.pixelSize: Theme.label; font.features: { "tnum": 1 }
                }
            }
            Rectangle {     // the onion skin shows it: before red, after green
                visible: f.side !== 0
                x: 2; width: parent.width - 4; height: 2; radius: 1; y: cell.y + cell.height + 1
                color: f.side < 0 ? Theme.danger : Theme.ok
            }
            MouseArea {     // click: go to it; drag: move (Alt: copy)
                id: area
                y: cell.y; height: cell.height        // never under 16 px wide: a narrow cell's area reaches under the next one
                visible: f.span !== null; x: f.span ? f.span[0] - f.x0 : 0; width: f.span ? f.span[1] - f.span[0] : 0
                acceptedButtons: Qt.LeftButton | Qt.RightButton; preventStealing: true; hoverEnabled: true
                cursorShape: moving ? Qt.ClosedHandCursor : Qt.PointingHandCursor
                HoverTip { hovered: area.containsMouse && !f.shows && !area.moving; text: "Drawing " + f.n }
                property real x0: 0
                property real dx: 0
                property bool moving: false
                property bool copying: false
                onPressed: (ev) => { x0 = mapToItem(m, ev.x, 0).x; dx = 0; moving = false; copying = ev.modifiers & Qt.AltModifier }
                onPositionChanged: (ev) => {
                    if (!pressed || pressedButtons !== Qt.LeftButton) return
                    const d = mapToItem(m, ev.x, 0).x - x0
                    if (Math.abs(d) > 4) moving = true
                    dx = m.framesOf(d) / m.fps * m.timeRuler.perSec     // whole frames
                }
                onReleased: (ev) => {
                    if (ev.button === Qt.RightButton) { cellMenu.open(); return }
                    const by = m.framesOf(dx)
                    if (backend.selected !== m.owner) backend.select(m.owner)
                    if (!moving) painter.goToFrame(f.at)
                    else if (by !== 0) copying ? painter.copyFrameTo(f.fid, f.at + by)
                                               : painter.moveFrame(f.fid, f.at + by)
                    moving = false; dx = 0
                }
                onCanceled: { moving = false; dx = 0 }
            }
            MouseArea {     // the right edge: hold longer or shorter, in whole frames (later drawings move with it)
                id: edge
                visible: f.grip       // narrower (or a key on it): = / − or zoom in (a handle must be 16 px to grab)
                x: parent.width - 16; width: 16; y: cell.y     // inside its own cell: never over the next one's; height: cell.height; z: 1
                cursorShape: Qt.SizeHorCursor; preventStealing: true
                property real x0: 0
                property real dx: 0
                onPressed: (ev) => { x0 = mapToItem(m, ev.x, 0).x; dx = 0 }
                onPositionChanged: (ev) => {
                    if (!pressed) return
                    const by = Math.max(1 - f.held, m.framesOf(mapToItem(m, ev.x, 0).x - x0))
                    dx = by / m.fps * m.timeRuler.perSec
                }
                onReleased: {
                    const by = m.framesOf(dx); dx = 0
                    if (backend.selected !== m.owner) backend.select(m.owner)
                    if (by !== 0) painter.holdFrame(f.fid, f.held + by)
                }
                onCanceled: dx = 0
            }
            Menu { id: cellMenu; y: cell.y + cell.height; entries: [{ value: "delete", label: "Delete" }]
                   onPicked: (v) => { if (backend.selected !== m.owner) backend.select(m.owner); painter.removeFrame(f.fid) } }
        }
    }
    Repeater {      // the layer's own ends: drag one to trim the layer (its start or end), as a bar's ends do
        model: m.trims && m.frames.length ? ["start", "end"] : []
        delegate: MouseArea {
            id: grab
            required property string modelData
            objectName: "cellEnd:" + m.owner + ":" + modelData
            property string held: ""
            readonly property bool atStart: modelData === "start"
            readonly property real edge: 8 + Math.round(m.timeRuler.xOf(atStart ? m.frames[0].t0 : m.frames[m.frames.length - 1].t1))
            x: atStart ? edge : edge - width - 1; width: 16; y: Math.round((m.height - 16) / 2); height: 16
            hoverEnabled: true; preventStealing: true; cursorShape: Qt.SizeHorCursor
            z: 3
            HoverTip { hovered: grab.containsMouse && !grab.held; text: grab.atStart ? "Drag to start the layer later or earlier" : "Drag to end the layer sooner or later" }
            function tAt(ev) { return m.timeRuler.tOf(mapToItem(m, ev.x, 0).x - 8) }
            onPressed: (ev) => { if (backend.selected !== m.owner) backend.select(m.owner)
                                 held = backend.beginBarDrag(m.owner, modelData, tAt(ev)) === false ? "" : modelData }
            onPositionChanged: (ev) => { if (held) backend.barDragTo(tAt(ev), (ev.modifiers & Qt.ControlModifier) ? 0 : 6 / m.timeRuler.perSec) }
            onReleased: { if (held) backend.endDrag(); held = "" }
            onCanceled: { if (held) backend.endDrag(); held = "" }
        }
    }
}
