import QtQuick
import RostrumKit

// The canvas: the engine's frame at the playhead (image://frame, rendered off the GUI thread), fitted on a
// neutral backdrop, with the selected layers' outlines (Handles.qml: a single layer also gets resize + turn handles).
// A press picks what is painted under it (screen2d/picking.py): the outermost group, or the piece once you are inside
// that group; Ctrl+press the piece itself; double-click goes one level in; Shift+click adds / removes. Dragging moves
// it (all selected layers together); dragging on empty canvas draws a rubber band that selects the layers it touches
// (boxSelect, not locked ones). One gesture = one undo step
// (backend.beginMove / moveBy / endDrag: one gesture = one undo step; an animated x / y gets a key at the playhead).
// With the Draw tool on (backend.tool, the tool strip at the top-left), a press draws instead: one stroke = one gesture =
// one undo step (painter.beginStroke / strokeTo / endStroke; on no drawing the first stroke makes one). A pen reports
// its pressure; a mouse is 1. The onion skin lies over the drawing's box. With the Pen tool on, PenOverlay takes the clicks.
Panel {
    id: panel
    title: "Canvas"
    readonly property var info: backend.frameInfo
    readonly property Item canvasFrame: frame      // the picture's box
    // The one mapping between composition px and this item's px (what sits over the canvas, e.g. the action bar, uses
    // it): compScale = screen px per composition px; compOrigin = where composition (0, 0) is; compView = the visible well.
    readonly property real compScale: well.fit
    readonly property point compOrigin: { frame.x; frame.y; well.width; well.height; width; height; return frame.mapToItem(panel, 0, 0) }
    readonly property rect compView: { well.width; well.height; width; height; const p = well.mapToItem(panel, 0, 0); return Qt.rect(p.x, p.y, well.width, well.height) }
    function toComp(x, y) { return Qt.point((x - compOrigin.x) / compScale, (y - compOrigin.y) / compScale) }
    function fromComp(x, y) { return Qt.point(compOrigin.x + x * compScale, compOrigin.y + y * compScale) }
    headerRight: Text { text: panel.info.width + " × " + panel.info.height + "  ·  " + panel.info.fps + " fps"
                        color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label }

    Rectangle {
        id: well
        anchors.fill: parent
        radius: Theme.radiusCtl; color: Theme.sunken
        readonly property bool drawing: backend.tool === "draw"
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
                var p = comp(m), mode = (m.modifiers & Qt.ControlModifier) ? "deep" : "click"
                var hit = backend.multi.target(p.x, p.y, mode)
                sx = m.x; sy = m.y; band = false; moving = false
                if (hit === "") { band = true; b0 = p; b1 = p; return }                         // nothing painted: a rubber band
                if (m.modifiers & Qt.ShiftModifier) backend.multi.toggle(hit)                   // Shift+click: add / remove
                else if (!backend.multi.has(hit)) backend.multi.pick(p.x, p.y, mode)            // else keep the selection and move it
                moving = backend.multi.has(hit) && backend.beginMove()
            }
            onDoubleClicked: (m) => { var p = comp(m); backend.multi.pick(p.x, p.y, "in") }   // one level into the group
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
        PenOverlay {  // the pen tool and the selected path's points (not while playing: they'd lag)
            anchors.fill: parent
            visible: !backend.playing && !well.drawing
            fit: well.fit; ox: frame.x; oy: frame.y
        }
        Item {  // outlines of the selected layers (turned with them) and the handles of a single one; over the pen's overlay
            id: marks
            x: frame.x; y: frame.y
            visible: !backend.playing           // they follow the playhead again when it stops (playback.py)
            Repeater {
                model: backend.multi.boxes
                delegate: Handles {
                    required property var modelData
                    box: modelData; fit: well.fit; space: marks
                    editable: backend.multi.count === 1 && !well.drawing && modelData.type !== "path" && !backend.pen.on
                }
            }
            Repeater {  // what an agent just changed: a 1-second outline in the agent colour (never moves the selection or the view)
                model: backend.agent.flash.filter(id => backend.rectOf(id).w !== undefined)
                delegate: ChangeOutline {
                    id: change
                    required property string modelData
                    readonly property var b: backend.rectOf(modelData)
                    x: (b.x || 0) * well.fit; y: (b.y || 0) * well.fit
                    width: (b.w || 0) * well.fit; height: (b.h || 0) * well.fit
                    transform: Rotation { origin.x: (change.b.ax || 0) * change.width; origin.y: (change.b.ay || 0) * change.height; angle: change.b.rot || 0 }
                }
            }
            Rectangle {  // the rubber band
                visible: canvas.band && (canvas.b0.x !== canvas.b1.x || canvas.b0.y !== canvas.b1.y)
                x: Math.min(canvas.b0.x, canvas.b1.x) * well.fit; y: Math.min(canvas.b0.y, canvas.b1.y) * well.fit
                width: Math.abs(canvas.b1.x - canvas.b0.x) * well.fit; height: Math.abs(canvas.b1.y - canvas.b0.y) * well.fit
                color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.12); border.width: 1; border.color: Theme.accent
            }
        }
        TapHandler {   // right-click: an unselected layer is selected alone first, a selected one keeps the selection
            acceptedButtons: Qt.RightButton
            enabled: backend.tool === "move"
            onTapped: (ev) => panel.openMenu(ev.position.x, ev.position.y)
        }
        ToolStrip { id: tools; anchors { left: parent.left; top: parent.top; margins: Theme.gap } }   // over everything on the canvas
        ContextBar {   // select, then act: the kit's bar at the top-centre, clear of the tool strip (backend.actions)
            hub: backend.actions
            anchors { top: parent.top; topMargin: Theme.gap; horizontalCenter: parent.horizontalCenter }
            maxWidth: well.width - 2 * (tools.width + 2 * Theme.gap)
            dragging: canvas.pressed || backend.tool !== "move" || backend.playing     // hidden while dragging or drawing
        }
    }
    ActionMenu { id: canvasMenu; onPicked: (v) => backend.run(v) }
    // The canvas's right-click menu at (x, y) in the well's px (default: the middle of the selection, for scripts).
    function openMenu(x, y) {
        if (x === undefined) {
            const b = backend.multi.boxes[0]
            const c = b ? Qt.point(frame.x + (b.x + b.w / 2) * well.fit, frame.y + (b.y + b.h / 2) * well.fit)
                        : Qt.point(well.width / 2, well.height / 2)
            x = c.x; y = c.y
        }
        const hit = backend.multi.target((x - frame.x) / well.fit, (y - frame.y) / well.fit, "click")
        const entries = backend.layerMenu(hit)
        if (!entries.length) return
        const g = well.mapToItem(null, x, y)
        canvasMenu.entries = entries
        canvasMenu.openAt(g.x, g.y)
    }
}
