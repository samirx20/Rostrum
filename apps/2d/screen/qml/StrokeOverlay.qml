import QtQuick
import QtQuick.Shapes
import RostrumKit

// What lies over the canvas while Draw is on besides the pen: the lasso being drawn, the picked strokes' outlines and
// box (backend.strokeSelect, composition px), and the colour picker's swatch while Alt is held (backend.colourPick).
// Input is the pen's (Stage.qml): Ctrl+drag or Select strokes then drag = lasso; a press in the picked box moves them;
// Alt+click picks the colour under the pointer; a press on a corner of the box scales the strokes about its centre, on
// the knob above it turns them (Shift: 15° steps), one undo step per drag (screen2d/stroke_handles.py). `fit`, `ox`, `oy`: this item's scale and where composition (0, 0) is.
// `cover`: what lies over the canvas (the context bar's rect); a knob that would sit under it, or off the top, goes
// below the box instead (sel.knobBelow, which the pen's hit test reads too).
Item {
    id: ov
    property real fit: 1
    property real ox: 0
    property real oy: 0
    property rect cover: Qt.rect(0, 0, 0, 0)
    property bool sizing: false                         // Alt + right-drag sizes the brush: only the ring shows, no swatch
    readonly property var sel: backend.strokeSelect
    readonly property var pick: backend.colourPick      // .swatch: the colour under the pointer while Alt is held; .at: where (composition px)

    Shape {
        x: ov.ox; y: ov.oy
        scale: ov.fit; transformOrigin: Item.TopLeft
        ShapePath {  // the lasso: a dashed loop
            strokeWidth: 1.5 / ov.fit; strokeColor: Theme.accent; fillColor: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.1)
            strokeStyle: ShapePath.DashLine; dashPattern: [4, 3]
            PathSvg { path: ov.sel.lassoPath }
        }
    }
    Repeater {  // the picked strokes, outlined
        model: ov.sel.outlines
        delegate: Shape {
            required property string modelData
            x: ov.ox; y: ov.oy
            scale: ov.fit; transformOrigin: Item.TopLeft
            ShapePath {
                strokeWidth: 2 / ov.fit; strokeColor: Theme.accent; fillColor: "transparent"
                PathSvg { path: modelData }
            }
        }
    }
    Rectangle {  // the box round them: a press inside moves them; its corners scale them, the knob above turns them
        id: handles
        readonly property var b: ov.sel.box
        visible: ov.sel.count > 0 && b.w !== undefined
        x: ov.ox + (b.x || 0) * ov.fit - 4; y: ov.oy + (b.y || 0) * ov.fit - 4
        width: (b.w || 0) * ov.fit + 8; height: (b.h || 0) * ov.fit + 8
        color: "transparent"; border.width: 1; border.color: Theme.accent
    }
    readonly property bool knobBelow: {
        const kx = handles.x + handles.width / 2, ky = handles.y - 24, m = 8
        return handles.visible && (ky < m || (kx > cover.x - m && kx < cover.x + cover.width + m
                                              && ky > cover.y - m && ky < cover.y + cover.height + m))
    }
    onKnobBelowChanged: sel.knobBelow = knobBelow
    component Grip: Rectangle { width: 9; height: 9; color: "white"; border.width: 1.5; border.color: Theme.accent; visible: handles.visible }
    Repeater {
        model: [[0, 0], [1, 0], [0, 1], [1, 1]]
        delegate: Grip {
            required property var modelData
            x: handles.x + modelData[0] * handles.width - width / 2; y: handles.y + modelData[1] * handles.height - height / 2
        }
    }
    Rectangle {  // the knob's stem
        visible: handles.visible
        x: handles.x + handles.width / 2 - 0.5; y: ov.knobBelow ? handles.y + handles.height : handles.y - 20; width: 1; height: 20; color: Theme.accent
    }
    Grip {  // the knob: 28 px above the strokes (stroke_geom.KNOB), or below them when the bar would cover it
        width: 11; height: 11; radius: 6
        x: handles.x + handles.width / 2 - width / 2
        y: (ov.knobBelow ? handles.y + handles.height + 24 : handles.y - 24) - height / 2
    }
    Rectangle {  // the picker: the colour under the pointer, beside it
        visible: ov.pick.alt && ov.pick.swatch !== "" && !ov.sizing
        x: ov.ox + ov.pick.at.x * ov.fit + 16; y: ov.oy + ov.pick.at.y * ov.fit + 16
        width: 28; height: 28; radius: 14
        color: ov.pick.swatch || "transparent"; border.width: 2; border.color: "white"
        Rectangle { anchors.fill: parent; anchors.margins: -1; radius: width / 2; color: "transparent"; border.width: 1; border.color: "#80000000" }
    }
}
