import QtQuick
import RostrumKit

// The canvas: the engine's frame at the playhead (image://frame, rendered off the GUI thread), fitted on a
// neutral backdrop, with the selected layers' outlines (Handles.qml: a single layer also gets resize + turn handles). Press on a layer
// selects it (Shift+click adds / removes); dragging moves it (all selected layers together); dragging on empty canvas draws a rubber band that
// selects the layers it touches (boxSelect). One gesture = one undo step
// (backend.beginMove / moveBy / endDrag: one gesture = one undo step; an animated x / y gets a key at the playhead).
// On the Draw page with a drawing layer selected, a press draws instead: one stroke = one gesture = one undo step
// (painter.beginStroke / strokeTo / endStroke). A pen reports its pressure; a mouse is 1. The onion skin lies over
// the drawing's box.
Panel {
    id: panel
    title: "Canvas"
    readonly property var info: backend.frameInfo
    headerRight: Text { text: panel.info.width + " × " + panel.info.height + "  ·  " + panel.info.fps + " fps"
                        color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label }

    Rectangle {
        id: well
        anchors.fill: parent
        radius: Theme.radiusCtl; color: Theme.sunken
        readonly property bool drawing: backend.page === "draw" && painter.drawingId !== ""
        readonly property real fit: Math.min((width - 48) / panel.info.width, (height - 48) / panel.info.height)

        Item {
            id: frame
            width: Math.round(panel.info.width * well.fit); height: Math.round(panel.info.height * well.fit)
            anchors.centerIn: parent
            Image {
                anchors.fill: parent
                source: backend.frame > 0 ? "image://frame/" + backend.frame : ""
                cache: false; smooth: true; mipmap: true
            }
            Image {  // onion skin: the neighbouring drawings, tinted, over the selected drawing's box
                readonly property var b: backend.selBox
                visible: painter.onionSerial > 0 && b.w !== undefined
                x: (b.x || 0) * well.fit; y: (b.y || 0) * well.fit
                width: (b.w || 0) * well.fit; height: (b.h || 0) * well.fit
                source: painter.onionSerial > 0 ? "image://onion/" + painter.onionSerial : ""
                cache: false; smooth: true
            }
            Rectangle {  // the frame's edge, so a dark composition still shows where it ends
                anchors.fill: parent; anchors.margins: -1
                color: "transparent"; border.width: 1; border.color: Theme.popupEdge
            }
        }
        Text {  // Draw page, nothing to draw on
            visible: backend.page === "draw" && painter.drawingId === ""
            anchors { horizontalCenter: parent.horizontalCenter; bottom: parent.bottom; bottomMargin: Theme.pad }
            text: "Select a drawing layer to draw on it"; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.body
        }
        Item {  // the pen
            anchors.fill: parent
            visible: well.drawing
            HoverHandler { cursorShape: Qt.CrossCursor }
            PointHandler {
                id: pen
                acceptedButtons: Qt.LeftButton
                function at() { return Qt.point((point.position.x - frame.x) / well.fit, (point.position.y - frame.y) / well.fit) }
                readonly property real pressure: point.pressure > 0 ? point.pressure : 1
                property bool drawing: false
                onActiveChanged: {
                    if (active) { var p = at(); drawing = painter.beginStroke(p.x, p.y, pressure) }
                    else { if (drawing) painter.endStroke(); drawing = false }
                }
                onPointChanged: { if (active && drawing) { var p = at(); painter.strokeTo(p.x, p.y, pressure) } }
            }
        }
        MouseArea {
            id: canvas
            anchors.fill: parent
            enabled: !well.drawing
            preventStealing: true
            property bool moving: false
            property bool band: false
            property real sx: 0
            property real sy: 0
            property point b0
            property point b1
            function comp(m) { return Qt.point((m.x - frame.x) / well.fit, (m.y - frame.y) / well.fit) }
            function stop() { if (moving) backend.endDrag(); moving = false; band = false }
            onPressed: (m) => {
                var p = comp(m), hit = backend.layerAt(p.x, p.y)
                sx = m.x; sy = m.y; band = false; moving = false
                if (hit === "") { band = true; b0 = p; b1 = p; return }                         // empty canvas: a rubber band
                if (m.modifiers & Qt.ShiftModifier) backend.multi.toggle(hit)                   // Shift+click: add / remove
                else if (!backend.multi.has(hit)) backend.pickAt(p.x, p.y)                      // else keep the selection and move it
                moving = backend.multi.has(hit) && backend.beginMove()
            }
            onPositionChanged: (m) => {
                if (moving) backend.moveBy((m.x - sx) / well.fit, (m.y - sy) / well.fit)
                else if (band) b1 = comp(m)
            }
            onReleased: (m) => {
                if (band) {
                    if (Math.abs(m.x - sx) + Math.abs(m.y - sy) < 4) backend.pickAt(b0.x, b0.y)   // a click: the composition
                    else backend.multi.boxSelect(b0.x, b0.y, b1.x, b1.y)
                }
                stop()
            }
            onCanceled: stop()
        }
        PenOverlay {  // Design page: the pen tool and the selected path's points
            anchors.fill: parent
            visible: backend.page === "design"
            fit: well.fit; ox: frame.x; oy: frame.y
        }
        Item {  // outlines of the selected layers (turned with them) and the handles of a single one; over the pen's overlay
            id: marks
            x: frame.x; y: frame.y
            Repeater {
                model: backend.multi.boxes
                delegate: Handles {
                    required property var modelData
                    box: modelData; fit: well.fit; space: marks
                    editable: backend.multi.count === 1 && !well.drawing && modelData.type !== "path" && !backend.pen.on
                }
            }
            Rectangle {  // the rubber band
                visible: canvas.band && (canvas.b0.x !== canvas.b1.x || canvas.b0.y !== canvas.b1.y)
                x: Math.min(canvas.b0.x, canvas.b1.x) * well.fit; y: Math.min(canvas.b0.y, canvas.b1.y) * well.fit
                width: Math.abs(canvas.b1.x - canvas.b0.x) * well.fit; height: Math.abs(canvas.b1.y - canvas.b0.y) * well.fit
                color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.12); border.width: 1; border.color: Theme.accent
            }
        }
    }
}
