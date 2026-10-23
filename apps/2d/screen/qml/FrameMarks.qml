import QtQuick
import RostrumKit

// Frame-by-frame on a timeline track: each drawing a cell as wide as it is held (`frames` from the layer's row:
// {id, n, at, held, t0, t1}), centred in the row like a layer's bar, two shades so neighbours read apart. The drawing
// at the playhead is lit (the accent, as a selected bar); the ones the onion skin shows have a red (before) or green
// (after) line under their cell. Sits in a track whose x is the ruler's x - 8, like the key diamonds.
// Click a cell: the playhead goes to it (it is the drawing painted into). Drag it: it moves to another frame (Alt: a
// copy goes there). Drag its right edge (a cell wide enough to grab it): it is held longer or shorter. Right-click: Delete. Each is one change (painter).
Item {
    id: m
    property var frames: []
    property var timeRuler
    property string owner: ""
    readonly property real fps: backend.frameInfo.fps || 30
    readonly property int cur: { for (const f of frames) if (backend.time >= f.t0 - 1e-6 && backend.time < f.t1 - 1e-6) return f.n; return 0 }
    readonly property bool onion: painter.onionOn && painter.drawingId === owner
    function framesOf(dx) { return Math.round(dx / m.timeRuler.perSec * m.fps) }
    Repeater {
        model: m.frames
        delegate: Item {
            id: f
            required property var modelData
            readonly property bool current: modelData.n === m.cur
            readonly property int side: !m.onion || m.cur === 0 ? 0
                : modelData.n < m.cur && m.cur - modelData.n <= painter.onionReach.before ? -1
                : modelData.n > m.cur && modelData.n - m.cur <= painter.onionReach.after ? 1 : 0
            readonly property bool last: modelData.n === m.frames.length
            x: 8 + Math.round(m.timeRuler.xOf(modelData.t0)) + (area.moving ? area.dx : 0)
            width: Math.max(3, Math.round(m.timeRuler.xOf(modelData.t1) - m.timeRuler.xOf(modelData.t0)) - 1 + edge.dx)
            height: m.height
            z: area.moving || edge.pressed ? 2 : 0
            Rectangle {     // the cell: the bar's height and roundness, centred
                id: cell
                objectName: "drawingCell" + f.modelData.n
                width: parent.width; height: 16; y: Math.round((parent.height - height) / 2); radius: 3
                color: f.current ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.30)
                     : f.modelData.n % 2 ? Theme.raised : Theme.hover
                border.width: f.current ? 1 : 0; border.color: Theme.accent
                opacity: area.moving && area.copying ? 0.6 : 1
                Text {
                    visible: parent.width > 16
                    x: 5; anchors.verticalCenter: parent.verticalCenter
                    text: f.modelData.n; color: f.current ? Theme.fg : Theme.fg2; font.family: uiFont
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
                width: Math.max(16, cell.width - (edge.visible ? 8 : 0))
                acceptedButtons: Qt.LeftButton | Qt.RightButton; preventStealing: true
                cursorShape: moving ? Qt.ClosedHandCursor : Qt.PointingHandCursor
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
                    if (!moving) painter.goToFrame(f.modelData.at)
                    else if (by !== 0) copying ? painter.copyFrameTo(f.modelData.id, f.modelData.at + by)
                                               : painter.moveFrame(f.modelData.id, f.modelData.at + by)
                    moving = false; dx = 0
                }
                onCanceled: { moving = false; dx = 0 }
            }
            MouseArea {     // the right edge: hold longer or shorter, in whole frames (later drawings move with it)
                id: edge
                visible: !f.last && f.width >= 32       // narrower: = / − or zoom in (a handle must be 16 px to grab)
                x: parent.width - 8; width: 16; y: cell.y; height: cell.height; z: 1
                cursorShape: Qt.SizeHorCursor; preventStealing: true
                property real x0: 0
                property real dx: 0
                onPressed: (ev) => { x0 = mapToItem(m, ev.x, 0).x; dx = 0 }
                onPositionChanged: (ev) => {
                    if (!pressed) return
                    const by = Math.max(1 - f.modelData.held, m.framesOf(mapToItem(m, ev.x, 0).x - x0))
                    dx = by / m.fps * m.timeRuler.perSec
                }
                onReleased: {
                    const by = m.framesOf(dx); dx = 0
                    if (backend.selected !== m.owner) backend.select(m.owner)
                    if (by !== 0) painter.holdFrame(f.modelData.id, f.modelData.held + by)
                }
                onCanceled: dx = 0
            }
            Menu { id: cellMenu; y: cell.y + cell.height; entries: [{ value: "delete", label: "Delete" }]
                   onPicked: (v) => { if (backend.selected !== m.owner) backend.select(m.owner); painter.removeFrame(f.modelData.id) } }
        }
    }
}
