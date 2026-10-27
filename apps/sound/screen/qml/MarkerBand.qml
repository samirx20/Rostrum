import QtQuick
import RostrumKit
import RostrumCursors 1.0
import "Picks.js" as Picks
import "Pointers.js" as Pointers
import "Tempo.js" as Tempo

// The named markers above the ruler, each a small tag at its time. Click selects the marker and puts the playhead on
// it; double-click (or F2, or M for a new one) opens its name field in place (Enter keeps, Esc cancels the renaming);
// right-click: its menu (marker_slots.py: Rename, Move to playhead, Colour, Put a sound here, Start a bar here…,
// Loop to the next marker, Delete; only what applies); its colour is the tag's edge; drag moves it
// (marker.set at, one gesture = one undo step; the ruler's snap: other markers, section edges, then the window's grid,
// with the snap line saying what it caught; Ctrl = free). The project's shared
// markers show with a dashed edge; dragging one moves only its tag while the mouse is down, and the release is one
// marker.move in the project's marker list (backend.moveSharedMarker), so it moves for every app.
// The pointer (the kit's CanvasCursor) is pick over a tag, the closed hand while one moves; the kit's chip by the
// pointer says where it lands ("bar 9.3"); Esc while dragging puts it back with no undo step (dragEsc).
// The clicks are taken here in one place, so a drag keeps going while the tags are redrawn.
Item {
    id: band
    objectName: "markerBand"
    property var ruler
    clip: true
    property string sharedId: ""    // the project marker being dragged (its tag follows the mouse until release)
    property real sharedDx: 0
    readonly property bool dragging: grab.dragging && grab.pressed && sharedId === ""    // the views show the snap line
    function tagWidth(name) { return metrics.advanceWidth(name) + 14 }
    // A tag near the band's right edge shifts left to end at the edge instead of being cut: its name stays whole (the line
    // through the rows stays at the marker's time). Pointer hits use the same place.
    function tagX(mx, w) { return mx < band.width ? Math.min(mx, Math.max(0, band.width - w)) : mx }
    function markerAt(x) {
        var best = null
        for (var i = 0; i < band.marks.length; i++) {
            var m = band.marks[i], mx = tagX(ruler.xOf(m.t), tagWidth(m.name))
            if (!m.named && x >= mx - 4 && x <= mx + tagWidth(m.name)) best = m
        }
        return best
    }
    function menuFor(id) {      // a scripted step's door to the same menu (layout check): open under that marker's tag
        var m = band.marks.find(k => k.id === id)
        markMenu.marker = id; markMenu.entries = backend.markerMenu(id)
        var q = mapToItem(null, ruler.xOf(m.t) + 6, height); markMenu.openAt(q.x, q.y)
    }
    FontMetrics { id: metrics; font.family: uiFont; font.pixelSize: Theme.label }

    readonly property var marks: backend.markers        // one read per change (each read copies the list)
    Repeater {   // by count: a tempo drag moves the markers without making them again
        model: band.marks.length
        delegate: Rectangle {
            required property int index
            readonly property var modelData: band.marks[index]
            readonly property bool on: !!Picks.heads(backend, backend.pickStamp)[modelData.id]
            readonly property bool naming: backend.renaming === modelData.id
            readonly property real at: Math.round(band.ruler.xOf(modelData.t) + (modelData.id === band.sharedId ? band.sharedDx : 0))
            x: Math.round(band.tagX(at, width)); y: 1
            visible: !modelData.named && x + width > 0 && at < band.width
            width: (naming ? Math.max(90, field.contentWidth + 10) : tag.implicitWidth) + 12; height: band.height - 2
            radius: 3; color: on ? Theme.accentFill : Theme.raised
            Rectangle { width: modelData.colour ? 3 : 2; height: parent.height; radius: 1
                        color: modelData.colour ? modelData.colour : parent.on ? Theme.fg : Theme.fg3
                        visible: !modelData.shared }
            Column { visible: modelData.shared; spacing: 2; Repeater { model: Math.ceil(band.height / 4)
                     Rectangle { width: 2; height: 2; color: Theme.accent } } }
            Text { id: tag; x: 7; anchors.verticalCenter: parent.verticalCenter; text: modelData.name; visible: !parent.naming
                   color: parent.on ? "white" : Theme.fg2; font.family: uiFont; font.pixelSize: Theme.label }
            NameBox {   // the name field, in place
                id: field
                objectName: "markerNameBox"
                visible: parent.naming; x: 7; width: parent.width - 10; anchors.verticalCenter: parent.verticalCenter
                font.pixelSize: Theme.label; selectionColor: Theme.app
                current: modelData.name; keepOnAway: true
                onDone: (t) => backend.finishRename(modelData.id, t)
                onCancelled: backend.finishRename(modelData.id, "")
                // Space before a letter is typed plays (M then Space: the name it was given stays, critic r12 #14);
                // once something is typed, it is a space in the name
                Keys.onSpacePressed: (e) => { if (text !== current) { e.accepted = false; return }
                                              backend.finishRename(modelData.id, ""); backend.togglePlay() }
            }
        }
    }
    MouseArea {
        id: grab
        anchors.fill: parent
        preventStealing: true
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        property real x0: 0
        property bool dragging: false
        property bool holding: false        // the drag holds Esc (dragEsc) once it has moved 4 px
        property string dragId: ""
        property real t0: 0
        hoverEnabled: true
        readonly property string pointer: holding ? "moving" : "pick"
        CanvasCursor { objectName: "markerCursor"; anchors.fill: parent; kind: Pointers.kind(grab.pointer) }
        function letGo() { if (holding) { holding = false; dragEsc.letEsc() } }
        Connections {   // Esc while a marker drag runs: it goes back, nothing written; the release then does nothing
            target: dragEsc
            function onCancelled() {
                if (!grab.holding) return
                grab.holding = false
                if (band.sharedId === "") backend.cancelDrag()
                band.sharedId = ""; band.sharedDx = 0; grab.dragging = false
            }
        }
        function landsAt() {   // where the dragged marker is now (a shared one: its tag, before the release)
            var k = band.marks.find(x => x.id === dragId)
            return k ? k.t + (band.sharedId !== "" ? band.sharedDx / band.ruler.perSec : 0) : t0
        }
        onDoubleClicked: (m) => { var hit = band.markerAt(m.x); if (hit !== null && !hit.shared) backend.startRename(hit.id) }
        onPressed: (m) => {
            var hit = band.markerAt(m.x)
            x0 = m.x; dragId = hit !== null ? hit.id : ""; t0 = hit !== null ? hit.t : 0
            if (m.button === Qt.RightButton) {      // a song marker's menu (Rename, Delete, Put a sound here …): the selection's
                if (hit === null || hit.shared) { m.accepted = false; return }
                markMenu.marker = hit.id; markMenu.entries = backend.markerMenu(hit.id)
                var q = mapToItem(null, m.x, m.y); markMenu.openAt(q.x, q.y)
                return
            }
            if (hit !== null && hit.shared) { band.sharedId = hit.id; band.sharedDx = 0; dragging = true; return }
            if (hit !== null) { backend.focusArea("arrange"); backend.setTime(hit.t) }    // clicking a marker: playhead on it
            dragging = hit !== null && backend.beginDrag(hit.id)
            if (!dragging) m.accepted = false
        }
        onPositionChanged: (m) => {
            if (!(dragging && pressed && (pressedButtons & Qt.LeftButton))) return
            if (!holding && Math.abs(m.x - x0) >= 4) { holding = true; dragEsc.holdEsc() }
            if (band.sharedId !== "") band.sharedDx = m.x - x0
            else backend.dragTo((m.x - x0) / band.ruler.perSec, 0, (m.modifiers & Qt.ControlModifier) !== 0, false, false, band.ruler.perSec)
        }
        onWheel: (w) => backend.viewWheel(w.angleDelta.x, w.angleDelta.y, (w.modifiers & Qt.ControlModifier) !== 0,
                                          (w.modifiers & Qt.ShiftModifier) !== 0, w.x / band.width, false)
        onReleased: (m) => {
            if (band.sharedId !== "")
                backend.moveSharedMarker(band.sharedId, band.sharedDx / band.ruler.perSec, (m.modifiers & Qt.ControlModifier) !== 0)
            else if (dragging) backend.endDrag()
            band.sharedId = ""; band.sharedDx = 0; dragging = false; letGo()
        }
        onCanceled: { if (dragging && band.sharedId === "") backend.cancelDrag(); band.sharedId = ""; band.sharedDx = 0; dragging = false; letGo() }
    }
    DragLabel {   // where the marker lands, as the ruler names it (over the band's parent: the band clips)
        parent: band.parent; z: 1000
        at: Qt.point(band.x + grab.mouseX, band.y + band.height / 2)
        text: grab.holding ? Tempo.barName(band.ruler.song, grab.landsAt()) : ""
    }
    ActionMenu { id: markMenu; objectName: "markerMenu"; property string marker: ""
                 onPicked: (v) => backend.markerPick(marker, v) }
}
