import QtQuick
import QtQuick.Shapes
import RostrumKit

// The creation tools over the canvas (screen2d/create.py does the work; the tool rail, R, O and T turn them on).
// A shape kind (Rectangle, Ellipse, Star, … backend.create.kinds): press-drag-release draws one (Shift = square / round,
// Alt = from the centre, a click = 200 px there); its box (an ellipse as an ellipse) and its size ("320 × 180") follow
// the pointer. A line or an arrow is dragged from its start to its end (Shift = 45° steps). Text: click and type, or drag a box to wrap in;
// a click outside, Esc or Ctrl+Enter ends (the text stays selected; no Done), Enter is a new line. Double-click a text
// (Stage.qml) or Enter with it selected (Main.qml) types in it again, on the canvas only.
// While typing the engine's own picture shows the words; the box here is transparent text with the cursor, lined up
// through the Stage's mapping only (compScale, fromComp, toComp). It lies in the canvas (Stage.qml).
Item {
    id: ov
    property Item stage
    readonly property var create: backend.create
    readonly property real scale: stage ? stage.compScale : 1
    readonly property string tool: backend.tool
    readonly property bool shapeTool: create.kinds.some(k => k.kind === tool)
    readonly property bool creating: shapeTool || tool === "text"
    readonly property var box: create.box
    readonly property var look: create.style
    // the one mapping (Stage.qml), from this overlay's own px (it lies in the canvas well)
    function toComp(x, y) { const q = ov.mapToItem(stage, x, y); return stage.toComp(q.x, q.y) }
    function fromComp(x, y) { const q = stage.fromComp(x, y); return ov.mapFromItem(stage, q.x, q.y) }
    function atMouse(m) { return ov.toComp(m.x, m.y) }

    MouseArea {
        id: area
        anchors.fill: parent
        enabled: (ov.creating || ov.create.typing) && !backend.playing && !spaceKey.held   // Space held: the view pans (ViewInput.qml)
        visible: enabled                                  // out of the way (and of the layout check) unless a creation tool is on
        cursorShape: Qt.CrossCursor
        preventStealing: true
        property point p0
        property real px: 0
        property real py: 0
        property bool shape: ov.shapeTool
        property bool ending: false                           // this press ended typing: its release makes nothing
        onPressed: (m) => {
            ending = ov.create.typing                         // a press here is outside the typing box (that takes its own):
            if (ending) return ov.create.commitText(editor.text)   // the text is made / kept, one change
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
            if (ov.create.typing || ending) return
            const p = ov.atMouse(m), moved = Math.abs(m.x - ov.fromComp(p0.x, p0.y).x) + Math.abs(m.y - ov.fromComp(p0.x, p0.y).y) > 4
            if (shape) ov.create.endShape(p.x, p.y, (m.modifiers & Qt.ShiftModifier) !== 0, (m.modifiers & Qt.AltModifier) !== 0)
            else if (moved) ov.create.beginText(Math.min(p0.x, p.x), Math.min(p0.y, p.y), Math.abs(p.x - p0.x))
            else ov.create.beginText(p0.x, p0.y, 0)
        }
        onCanceled: if (shape) ov.create.endShape(p0.x, p0.y, false, false)
    }
    Item {              // the shape being drawn (an ellipse as an ellipse)
        id: shapeBox
        readonly property bool on: ov.box.kind !== undefined && ov.box.kind !== "text" && ov.box.x0 === undefined
        visible: on
        x: on ? ov.fromComp(ov.box.x, ov.box.y).x : 0; y: on ? ov.fromComp(ov.box.x, ov.box.y).y : 0
        width: on ? ov.box.w * ov.scale : 0; height: on ? ov.box.h * ov.scale : 0
        readonly property color wash: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.15)
        HaloLine { visible: ov.box.kind !== "ellipse"; anchors.fill: parent; lineWidth: 1.5; fillOpacity: 0.15 }
        Shape {
            visible: ov.box.kind === "ellipse"; anchors.fill: parent
            ShapePath {
                strokeColor: Theme.accent; strokeWidth: 1.5; fillColor: shapeBox.wash
                PathAngleArc { centerX: shapeBox.width / 2; centerY: shapeBox.height / 2; radiusX: Math.max(0.5, shapeBox.width / 2); radiusY: Math.max(0.5, shapeBox.height / 2)
                               startAngle: 0; sweepAngle: 360 }
            }
        }
    }
    Shape {             // a line or an arrow being drawn: start to end
        id: along
        readonly property bool on: ov.box.x0 !== undefined
        visible: on
        readonly property point a: on ? ov.fromComp(ov.box.x0, ov.box.y0) : Qt.point(0, 0)
        readonly property point b: on ? ov.fromComp(ov.box.x1, ov.box.y1) : Qt.point(0, 0)
        ShapePath { strokeColor: Theme.accent; strokeWidth: 2; fillColor: "transparent"; capStyle: ShapePath.RoundCap
                    startX: along.a.x; startY: along.a.y; PathLine { x: along.b.x; y: along.b.y } }
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
        width: on ? (ov.box.wrap ? ov.box.w * ov.scale : Math.max(ov.box.w * ov.scale, words.contentWidth) + 4) : 0     // the words' own width, measured apart: edit.contentWidth reads back this width (binding loop)
        height: on ? Math.max(ov.box.h * ov.scale, edit.contentHeight) : 0
        property alias text: edit.text
        Text { id: words; visible: false; text: edit.text; font: edit.font }     // the one place the typed width is measured
        HaloLine { anchors.fill: parent; anchors.margins: -4; radius: 2 }
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
