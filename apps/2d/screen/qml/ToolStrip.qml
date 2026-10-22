import QtQuick
import RostrumKit

// The canvas's tools, floating at its top-left: what the mouse does on the canvas (backend.tool, screen state).
// Move (V): select, move, the handles. Pen (P): click and drag points into a new path. Draw (B): paint strokes; the
// inspector shows the brush while it is on.
// Rectangle (R), Ellipse (O), Text (T): drag a shape / click or drag a box and type (CreateOverlay.qml). The one switch is backend.setTool; Esc goes back to Move (Main.qml).
Rectangle {
    id: strip
    objectName: "toolStrip"           // CreateOverlay leaves this rectangle to the buttons
    readonly property var tools: [{ value: "move", label: "Move", key: "V" }, { value: "pen", label: "Pen", key: "P" },
                                  { value: "draw", label: "Draw", key: "B" },
                                  { value: "rect", label: "Rectangle", key: "R" }, { value: "ellipse", label: "Ellipse", key: "O" },
                                  { value: "text", label: "Text", key: "T" }]
    width: column.width + 2 * Theme.grid; height: column.height + 2 * Theme.grid
    radius: Theme.radiusPanel; color: Theme.panel
    border.width: 1; border.color: Theme.popupEdge

    Column {
        id: column
        x: Theme.grid; y: Theme.grid
        spacing: 2
        Repeater {
            model: strip.tools
            delegate: Button {
                required property var modelData
                kind: "ghost"; width: 92
                text: modelData.label; hint: modelData.key
                down: backend.tool === modelData.value
                onClicked: backend.setTool(modelData.value)
            }
        }
    }
}
