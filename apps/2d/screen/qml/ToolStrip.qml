import QtQuick
import RostrumKit

// The canvas's tools, floating at its top-left: what the mouse does on the canvas (backend.tool, screen state).
// Move (V): select, move, the handles. Pen (P): click and drag points into a new path. Draw (B): paint strokes; the
// inspector shows the brush while it is on.
// Rectangle (R), Ellipse (O), Text (T): drag a shape / click or drag a box and type (CreateOverlay.qml). The one switch is backend.setTool; Esc goes back to Move (Main.qml).
Rectangle {
    id: strip
    property alias addMenu: addBtn
    objectName: "toolStrip"           // CreateOverlay leaves this rectangle to the buttons
    // job: the key map job (the key shown comes from the map: AppShell.keyFor); help: the hover help's sentence
    readonly property var tools: [
        { value: "move", label: "Move", job: "move_tool", help: "Pick layers, move them, and drag their handles." },
        { value: "pen", label: "Pen", job: "pen_tool", help: "Click and drag points to draw a path." },
        { value: "draw", label: "Draw", job: "paint_tool", help: "Paint strokes with a brush, on a drawing or on the selected layer." },
        { value: "rect", label: "Rectangle", job: "rect_tool", help: "Drag out a rectangle." },
        { value: "ellipse", label: "Ellipse", job: "ellipse_tool", help: "Drag out an ellipse." },
        { value: "text", label: "Text", job: "text_tool", help: "Click or drag a box on the canvas, then type." },
        { value: "camera", label: "Camera", job: "camera_tool", needsCamera: true,
          help: "Drag to pan the camera; hold Alt and drag up to push in, down to pull out." },
        { value: "bone", label: "Bone", job: "bone_tool", needsRig: true,
          help: "Click joint after joint (or drag from a joint to the tip) to draw the rig's bones. Esc ends the chain." }]
    width: column.width + 2 * Theme.grid; height: column.height + 2 * Theme.grid
    radius: Theme.radiusPanel; color: Theme.panel
    border.width: 1; border.color: Theme.popupEdge

    Column {
        id: column
        x: Theme.grid; y: Theme.grid
        spacing: 2
        Repeater {
            model: strip.tools.filter(t => (!t.needsCamera || backend.cameraTool.available) && (!t.needsRig || backend.boneTool.available))   // Camera: only when the scene has one; Bone: while a rig is in hand
            delegate: Button {
                required property var modelData
                kind: "ghost"; width: 92
                text: modelData.label; help: modelData.help; job: modelData.job
                hint: Window.window.keyFor(modelData.job)
                down: backend.tool === modelData.value
                onClicked: backend.setTool(modelData.value)
            }
        }
        AddMenu { id: addBtn }     // "+" at the foot: Import…, Camera, 3D render, Library
    }
}
