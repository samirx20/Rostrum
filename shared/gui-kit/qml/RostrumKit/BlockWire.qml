import QtQuick
import QtQuick.Shapes

// One wire of the block view: a smooth cubic from an output (x1, y1) to an input (x2, y2), in canvas units, leaving
// and arriving level. Its ends are bindings on the two blocks' positions, so moving a block redraws only its own wires.
// The curve renderer draws it smooth at every zoom without multisampling the whole view.
Shape {
    id: w
    property real x1: 0
    property real y1: 0
    property real x2: 0
    property real y2: 0
    property color colour: "#a3a9b3"
    property real thickness: 2
    readonly property real bend: Math.max(36, Math.abs(x2 - x1) * 0.5)
    preferredRendererType: Shape.CurveRenderer
    ShapePath {
        strokeColor: w.colour
        strokeWidth: w.thickness
        fillColor: "transparent"
        capStyle: ShapePath.RoundCap
        startX: w.x1; startY: w.y1
        PathCubic {
            x: w.x2; y: w.y2
            control1X: w.x1 + w.bend; control1Y: w.y1
            control2X: w.x2 - w.bend; control2Y: w.y2
        }
    }
}
