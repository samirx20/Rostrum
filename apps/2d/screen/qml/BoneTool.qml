import QtQuick
import QtQuick.Shapes
import RostrumKit
import RostrumCursors 1.0

// The Bone tool over the canvas (screen2d/bone_tool.py does the work; J or the tool rail, only with a rig in hand).
// Click joint after joint, or press at a joint and drag to the bone's tip: each bone is one change, and the next starts
// at its tip. A press on a joint the rig has starts there (a branch). Esc ends the chain (Main.qml). The line from the
// chain's end to the pointer shows the bone a click would make. Points go through the Stage's mapping (composition px).
Item {
    id: ov
    property Item stage
    readonly property var tool: backend.boneTool
    readonly property bool on: backend.tool === "bone" && !backend.playing
    readonly property real near: 8 / (stage ? stage.compScale : 1)      // a joint is caught within 8 screen px
    function toComp(x, y) { const q = ov.mapToItem(stage, x, y); return stage.toComp(q.x, q.y) }
    function fromComp(x, y) { const q = stage.fromComp(x, y); return ov.mapFromItem(stage, q.x, q.y) }

    MouseArea {
        anchors.fill: parent
        enabled: ov.on && !spaceKey.held         // Space held: the view pans (ViewInput.qml)
        visible: enabled
        hoverEnabled: true
        preventStealing: true
        CanvasCursor { anchors.fill: parent; kind: "make" }        // a new bone (CURSORS.md)
        property bool going: false
        onPressed: (m) => { const p = ov.toComp(m.x, m.y); going = ov.tool.press(p.x, p.y, ov.near) }
        onPositionChanged: (m) => { const p = ov.toComp(m.x, m.y); ov.tool.hover(p.x, p.y) }
        onReleased: (m) => { if (going) { const p = ov.toComp(m.x, m.y); ov.tool.release(p.x, p.y, ov.near) } going = false }
        onCanceled: going = false
    }
    Shape {         // the bone the pointer would make: a dashed line from the joint
        id: rubber
        visible: ov.on && ov.tool.line.length === 4
        readonly property point a: visible ? ov.fromComp(ov.tool.line[0], ov.tool.line[1]) : Qt.point(0, 0)
        readonly property point b: visible ? ov.fromComp(ov.tool.line[2], ov.tool.line[3]) : Qt.point(0, 0)
        ShapePath {
            strokeWidth: 2; strokeColor: Theme.accent; fillColor: "transparent"
            strokeStyle: ShapePath.DashLine; dashPattern: [4, 3]
            startX: rubber.a.x; startY: rubber.a.y
            PathLine { x: rubber.b.x; y: rubber.b.y }
        }
    }
    Rectangle {     // the chain's end: where the next bone starts
        visible: ov.on && ov.tool.line.length === 4
        readonly property point a: visible ? ov.fromComp(ov.tool.line[0], ov.tool.line[1]) : Qt.point(0, 0)
        x: a.x - 5; y: a.y - 5; width: 10; height: 10; radius: 5
        color: Theme.accent; border.width: 1.5; border.color: "white"
    }
}
