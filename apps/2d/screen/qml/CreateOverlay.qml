import QtQuick
import QtQuick.Shapes
import RostrumKit

// The creation tools over the canvas (screen2d/create.py does the work; the tool strip, R, O and T turn them on).
// Rectangle / Ellipse: press-drag-release draws one (Shift = square / round, Alt = from the centre, a click = 200 px
// there); the outline and its size ("320 × 180") follow the pointer. Text: click and type, or drag a box to wrap in;
// Esc or Ctrl+Enter ends (the text stays selected), Enter is a new line. Double-click a text (Move) to type in it again.
// While typing the engine's own picture shows the words; the box here is transparent text with the cursor, lined up
// through the Stage's mapping only (compScale, fromComp, toComp). It lies in the canvas, under the tool strip (Stage.qml).
Item {
    id: ov
    property Item stage
    readonly property var create: backend.create
    readonly property real scale: stage ? stage.compScale : 1
    readonly property string tool: backend.tool
    readonly property bool creating: tool === "rect" || tool === "ellipse" || tool === "text"
    readonly property var box: create.box
    readonly property var look: create.style
    // the one mapping (Stage.qml), from this overlay's own px (it lies in the canvas well, under the tool strip)
    function toComp(x, y) { const q = ov.mapToItem(stage, x, y); return stage.toComp(q.x, q.y) }
    function fromComp(x, y) { const q = stage.fromComp(x, y); return ov.mapFromItem(stage, q.x, q.y) }
    function atMouse(m) { return ov.toComp(m.x, m.y) }

    MouseArea {
        id: area
        anchors.fill: parent
        enabled: ov.creating && !backend.playing && !spaceKey.held     // Space held: the view pans (ViewInput.qml)
        visible: enabled                                  // out of the way (and of the layout check) unless a creation tool is on
        cursorShape: Qt.CrossCursor
        preventStealing: true
        property point p0
        property real px: 0
        property real py: 0
        property bool shape: ov.tool === "rect" || ov.tool === "ellipse"
        onPressed: (m) => {
            if (ov.create.typing) return                      // the click that ends typing is handled by `ender` below
            p0 = ov.atMouse(m); px = m.x; py = m.y
            if (shape) ov.create.beginShape(ov.tool, p0.x, p0.y, 4 / ov.scale)
        }
        onPositionChanged: (m) => {
            px = m.x; py = m.y
            if (pressed && shape && !ov.create.typing) {
                const p = ov.atMouse(m)
                ov.create.dragShape(p.x, p.y, (m.modifiers & Qt.ShiftModifier) !== 0, (m.modifiers & Qt.AltModifier) !== 0)
            }
        }
        onReleased: (m) => {
            if (ov.create.typing) return
            const p = ov.atMouse(m), moved = Math.abs(m.x - ov.fromComp(p0.x, p0.y).x) + Math.abs(m.y - ov.fromComp(p0.x, p0.y).y) > 4
            if (shape) ov.create.endShape(p.x, p.y, (m.modifiers & Qt.ShiftModifier) !== 0, (m.modifiers & Qt.AltModifier) !== 0)
            else if (moved) ov.create.beginText(Math.min(p0.x, p.x), Math.min(p0.y, p.y), Math.abs(p.x - p0.x))
            else ov.create.beginText(p0.x, p0.y, 0)
        }
        onCanceled: if (shape) ov.create.endShape(p0.x, p0.y, false, false)
    }
    PointHandler {      // passive, the press goes on: a press outside the typing box ends typing (the text stays);
        id: ender       // two quick presses on a text with the Move tool = double-click: type in it (Stage's click selects)
        acceptedButtons: Qt.LeftButton
        property real lastAt: 0
        property point lastPos
        onActiveChanged: {
            if (!active) return
            const x = point.position.x, y = point.position.y
            if (ov.create.typing) {
                const q = editor.mapFromItem(ov, x, y)
                if (q.x < -6 || q.y < -6 || q.x > editor.width + 6 || q.y > editor.height + 6) ov.create.commitText(editor.text)
                return
            }
            const now = Date.now()
            if (ov.tool === "move" && now - lastAt < 450 && Math.abs(x - lastPos.x) + Math.abs(y - lastPos.y) < 6) {
                const p = ov.toComp(x, y)
                ov.create.editAt(p.x, p.y)
                lastAt = 0
            } else { lastAt = now; lastPos = Qt.point(x, y) }
        }
    }
    Item {              // the shape being drawn (an ellipse as an ellipse)
        id: shapeBox
        readonly property bool on: ov.box.kind === "rect" || ov.box.kind === "ellipse"
        visible: on
        x: on ? ov.fromComp(ov.box.x, ov.box.y).x : 0; y: on ? ov.fromComp(ov.box.x, ov.box.y).y : 0
        width: on ? ov.box.w * ov.scale : 0; height: on ? ov.box.h * ov.scale : 0
        readonly property color wash: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.15)
        Rectangle { visible: ov.box.kind === "rect"; anchors.fill: parent; color: shapeBox.wash; border.width: 1.5; border.color: Theme.accent }
        Shape {
            visible: ov.box.kind === "ellipse"; anchors.fill: parent
            ShapePath {
                strokeColor: Theme.accent; strokeWidth: 1.5; fillColor: shapeBox.wash
                PathAngleArc { centerX: shapeBox.width / 2; centerY: shapeBox.height / 2; radiusX: Math.max(0.5, shapeBox.width / 2); radiusY: Math.max(0.5, shapeBox.height / 2)
                               startAngle: 0; sweepAngle: 360 }
            }
        }
    }
    Rectangle {         // the live size, by the pointer
        visible: ov.box.label !== undefined
        readonly property point at: area.pressed ? Qt.point(area.px + 16, area.py + 16)
                                  : ov.fromComp(ov.box.x + ov.box.w + 8 / ov.scale, ov.box.y + ov.box.h + 8 / ov.scale)
        x: Math.min(at.x, ov.width - width - Theme.grid); y: Math.min(at.y, ov.height - height - Theme.grid)
        width: sizeText.width + 2 * Theme.grid; height: sizeText.height + Theme.grid
        radius: Theme.radiusCtl; color: Theme.raised; border.width: 1; border.color: Theme.popupEdge
        Text { id: sizeText; anchors.centerIn: parent; text: ov.box.label || ""; color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.label }
    }

    Item {              // typing: the box and the cursor, over the engine's picture of the words
        id: editor
        readonly property bool on: ov.create.typing && ov.box.kind === "text"
        visible: on
        x: on ? ov.fromComp(ov.box.x, ov.box.y).x : 0; y: on ? ov.fromComp(ov.box.x, ov.box.y).y : 0
        width: on ? (ov.box.wrap ? ov.box.w * ov.scale : Math.max(ov.box.w * ov.scale, edit.contentWidth) + 4) : 0
        height: on ? Math.max(ov.box.h * ov.scale, edit.contentHeight) : 0
        property alias text: edit.text
        Rectangle { anchors.fill: parent; anchors.margins: -4; color: "transparent"; border.width: 1; border.color: Theme.accent; radius: 2 }
        TextEdit {
            id: edit
            anchors.fill: parent
            color: "transparent"; selectionColor: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.45); selectedTextColor: "transparent"
            font.family: ov.look.font || uiFont
            font.pixelSize: Math.max(4, (ov.look.size || 40) * ov.scale)
            font.weight: Math.max(1, Math.min(1000, ov.look.weight || 600))
            wrapMode: ov.box.wrap ? TextEdit.Wrap : TextEdit.NoWrap
            persistentSelection: true
            property bool loading: false
            cursorDelegate: Item { }                     // drawn below (it shows with or without window focus)
            // Qt's font is not the engine's: squeeze / stretch the line so the cursor sits where the engine's letters end
            readonly property real fitX: !ov.box.wrap && contentWidth > 8 && ov.box.w > 0 ? Math.max(0.6, Math.min(1.7, ov.box.w * ov.scale / contentWidth)) : 1
            transform: Scale { xScale: edit.fitX; yScale: 1 }
            Rectangle {     // the cursor: on a moment after every key, then blinking
                id: caret
                property bool lit: true
                x: edit.cursorRectangle.x; y: edit.cursorRectangle.y; width: 2; height: edit.cursorRectangle.height
                color: Theme.accent; visible: lit                      // blinks (the proof pictures hold it on)
                Connections { target: edit; function onTextChanged() { caret.lit = true; blink.restart() } }
                Timer { id: blink; interval: 530; repeat: true; running: editor.on; onTriggered: caret.lit = !caret.lit }
            }
            onTextChanged: if (!loading && ov.create.typing) ov.create.typeText(text)
            Keys.onEscapePressed: ov.create.commitText(text)
            Keys.onPressed: (e) => {
                if ((e.key === Qt.Key_Return || e.key === Qt.Key_Enter) && (e.modifiers & Qt.ControlModifier)) { ov.create.commitText(text); e.accepted = true }
            }
        }
        Connections {   // words typed through the operation (an agent, a scripted walk) show in the box too
            target: ov.create
            function onTypingChanged() {
                if (editor.on && edit.text !== ov.create.body) { edit.loading = true; edit.text = ov.create.body; edit.loading = false; edit.cursorPosition = edit.length }
            }
        }
        onOnChanged: if (on) { edit.loading = true; edit.text = ov.create.body; edit.loading = false; edit.forceActiveFocus(); edit.selectAll() }
    }
}
