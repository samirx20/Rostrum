import QtQuick
import QtQuick.Shapes
import RostrumKit

// What lies over the canvas while Draw is on besides the pen: the lasso being drawn, the picked strokes' outlines and
// box (backend.strokeSelect, composition px), and the colour picker's swatch while Alt is held (backend.colourPick).
// Input is the pen's (Stage.qml): Ctrl+drag or Select strokes then drag = lasso; a press in the picked box moves them;
// Alt+click picks the colour under the pointer. The box's own handles take their presses first: a corner scales the
// strokes about the box's centre, the knob above turns them (Shift: 15° steps); each drag is one undo step
// (screen2d/stroke_handles.py). `fit`, `ox`, `oy`: this item's scale and where composition (0, 0) is.
Item {
    id: ov
    property real fit: 1
    property real ox: 0
    property real oy: 0
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
    Rectangle {  // the box round them: a press inside moves them
        readonly property var b: ov.sel.box
        visible: ov.sel.count > 0 && b.w !== undefined
        x: ov.ox + (b.x || 0) * ov.fit - 4; y: ov.oy + (b.y || 0) * ov.fit - 4
        width: (b.w || 0) * ov.fit + 8; height: (b.h || 0) * ov.fit + 8
        color: "transparent"; border.width: 1; border.color: Theme.accent
    }
    component Grip: MouseArea {
        id: grip
        property string kind: "scale"
        width: 18; height: 18
        hoverEnabled: true; preventStealing: true
        function comp(m) { const p = grip.mapToItem(ov, m.x, m.y); return Qt.point((p.x - ov.ox) / ov.fit, (p.y - ov.oy) / ov.fit) }
        onPressed: (m) => { const p = comp(m); ov.sel.beginHandle(kind, p.x, p.y) }
        onPositionChanged: (m) => { if (pressed) { const p = comp(m); ov.sel.handleTo(p.x, p.y, (m.modifiers & Qt.ShiftModifier) !== 0) } }
        onReleased: ov.sel.endHandle()
        onCanceled: ov.sel.endHandle()
    }
    Item {  // the handles: four corners scale (the knob above the top edge, below, turns)
        id: handles
        readonly property var b: ov.sel.box
        visible: ov.sel.count > 0 && b.w !== undefined
        x: ov.ox + (b.x || 0) * ov.fit - 4; y: ov.oy + (b.y || 0) * ov.fit - 4
        width: (b.w || 0) * ov.fit + 8; height: (b.h || 0) * ov.fit + 8
        Repeater {
            model: [[0, 0], [1, 0], [0, 1], [1, 1]]
            delegate: Grip {
                required property var modelData
                x: modelData[0] * handles.width - width / 2; y: modelData[1] * handles.height - height / 2
                cursorShape: modelData[0] === modelData[1] ? Qt.SizeFDiagCursor : Qt.SizeBDiagCursor
                Rectangle { anchors.centerIn: parent; width: 9; height: 9; color: "white"; border.width: 1.5; border.color: Theme.accent }
            }
        }
    }
    Rectangle {  // the knob's stem (the knob is the overlay's own child: a press outside its parent's area never reaches it)
        visible: handles.visible
        x: handles.x + handles.width / 2 - 0.5; y: handles.y - 20; width: 1; height: 20; color: Theme.accent
    }
    Grip {
        kind: "turn"
        visible: handles.visible
        x: handles.x + handles.width / 2 - width / 2; y: handles.y - 24 - height / 2     // 28 px above the box (stroke_geom.KNOB)
        cursorShape: Qt.CrossCursor
        Rectangle { anchors.centerIn: parent; width: 11; height: 11; radius: 6; color: "white"; border.width: 1.5; border.color: Theme.accent }
    }
    Rectangle {  // the picker: the colour under the pointer, beside it
        visible: ov.pick.alt && ov.pick.swatch !== ""
        x: ov.ox + ov.pick.at.x * ov.fit + 16; y: ov.oy + ov.pick.at.y * ov.fit + 16
        width: 28; height: 28; radius: 14
        color: ov.pick.swatch || "transparent"; border.width: 2; border.color: "white"
        Rectangle { anchors.fill: parent; anchors.margins: -1; radius: width / 2; color: "transparent"; border.width: 1; border.color: "#80000000" }
    }
}
