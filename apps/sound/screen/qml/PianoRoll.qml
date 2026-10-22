import QtQuick
import RostrumKit

// Timeline page, centre: the selection's track up close. Notes: bars on a keyboard (drag = time and pitch,
// double-click empty space = a new note, Delete removes). Drums: one row per drum. Recorded clips: their
// waveforms. One gesture per drag = one undo step; a quarter beat grid, Shift = free.
Panel {
    id: p
    readonly property var roll: backend.roll
    readonly property string kind: roll.kind
    readonly property int keysWidth: 52
    title: roll.name !== "" ? roll.name : "Piano roll"
    headerRight: [
        PictureToggle { anchors.verticalCenter: parent.verticalCenter },
        Text { anchors.verticalCenter: parent.verticalCenter; rightPadding: Theme.grid
               text: p.kind === "notes" ? "Double-click to add a note  ·  Shift drags freely  ·  Ctrl + wheel zooms"
                   : p.kind === "drums" || p.kind === "audio" ? "Shift drags freely" : ""
               color: Theme.fg4; font.family: uiFont; font.pixelSize: Theme.label }
    ]

    BarRuler {
        id: bars
        visible: p.kind !== "none" && p.kind !== "empty"
        x: p.keysWidth; width: parent.width - x; height: 22
    }
    Rectangle {
        id: well
        visible: bars.visible
        anchors { left: parent.left; right: parent.right; top: bars.bottom; bottom: parent.bottom; topMargin: Theme.grid }
        radius: Theme.radiusCtl; color: Theme.sunken; clip: true

        Flickable {
            id: view
            anchors.fill: parent
            contentHeight: grid.height; boundsBehavior: Flickable.StopAtBounds; interactive: false
            RollGrid { id: grid; width: view.width; viewHeight: view.height; roll: p.roll; ruler: bars; keysWidth: p.keysWidth }
            MouseArea {   // every click and drag on the roll, in one place
                x: p.keysWidth; width: grid.width - x; height: grid.height
                preventStealing: true
                property real x0: 0
                property real y0: 0
                property bool dragging: false
                onWheel: (w) => {   // Ctrl zooms, Shift / sideways scrolls in time (the Timeline's view); else up and down
                    if (!backend.viewWheel(w.angleDelta.x, w.angleDelta.y, (w.modifiers & Qt.ControlModifier) !== 0,
                                           (w.modifiers & Qt.ShiftModifier) !== 0, w.x / width, true))
                        view.contentY = Math.max(0, Math.min(view.contentHeight - view.height, view.contentY - w.angleDelta.y / 2))
                }
                PinchGrow {}
                onPressed: (m) => {
                    var id = backend.rollAt(bars.tOf(m.x), grid.rowAt(m.y), 6 / bars.perSec)
                    x0 = m.x; y0 = m.y
                    dragging = id !== "" && backend.beginDrag(id)
                }
                onPositionChanged: (m) => { if (dragging) backend.dragBy((m.x - x0) / bars.perSec,
                    p.kind === "notes" ? -Math.round((m.y - y0) / grid.rowH) : 0, (m.modifiers & Qt.ShiftModifier) !== 0) }
                onReleased: { if (dragging) backend.endDrag(); dragging = false }
                onCanceled: { if (dragging) backend.cancelDrag(); dragging = false }
                onDoubleClicked: (m) => { if (p.kind === "notes" && backend.rollAt(bars.tOf(m.x), grid.rowAt(m.y), 0) === "")
                                              backend.addNote(bars.tOf(m.x), Math.round(grid.rowAt(m.y))) }
            }
            Component.onCompleted: centre()
            function centre() {   // the notes in view
                var ks = [], b = p.roll.blocks
                for (var i = 0; i < b.length; i++) if (b[i].keys) ks = ks.concat(b[i].keys)
                if (!ks.length || p.kind !== "notes") { contentY = 0; return }
                var mid = (Math.max.apply(null, ks) + Math.min.apply(null, ks)) / 2
                contentY = Math.max(0, Math.min(contentHeight - height, (p.roll.hi - mid) * grid.rowH - height / 2))
            }
            Connections { target: p; function onKindChanged() { view.centre() } }
        }
        Repeater {   // marker lines
            model: backend.markers
            delegate: Rectangle { required property var modelData
                x: p.keysWidth + Math.round(bars.xOf(modelData.t)); width: 1; height: well.height
                visible: bars.visibleX(x - p.keysWidth); color: Theme.fg4; opacity: 0.6 }
        }
        Rectangle { x: p.keysWidth + Math.round(bars.xOf(backend.time)); width: 1; height: well.height
                    visible: bars.visibleX(x - p.keysWidth); color: Theme.accent; opacity: 0.9 }
    }
    Column {   // nothing to draw: say what to do, calmly
        visible: !bars.visible
        anchors.centerIn: parent; spacing: Theme.gap
        Text { anchors.horizontalCenter: parent.horizontalCenter; font.family: uiFont; font.pixelSize: Theme.title
               color: Theme.fg2; text: p.kind === "none" ? "No track yet" : "Nothing on this track yet" }
        Text { anchors.horizontalCenter: parent.horizontalCenter; font.family: uiFont; font.pixelSize: Theme.body
               color: Theme.fg3
               text: p.kind === "none" ? "Add a track with + Track at the top, then select it to see its notes here."
                     : recorder.armed !== "" ? "Press Record (R) to record a take on this track."
                     : "To record: press Rec on the track's row, then press R.
To write notes: choose an instrument in the inspector." 
               horizontalAlignment: Text.AlignHCenter }
    }
}
