import QtQuick
import RostrumKit
import RostrumCursors 1.0

// The Pose tool on the viewport (screen3d/pose_qt.py has the state, pose_drag.py the pointer, pose_view.py the maths).
// While Pose is on: the clay's bones as thin lines posed at the playhead (the ones a drag would turn in the accent,
// from the hover), a small dot on each joint, an orange ring on each hold. A left drag on the clay poses it (Esc mid-
// drag puts it back), a click holds that spot (or lets go), a ring drags to a new spot or lets go on a click, Alt +
// a joint dot drags the joint; off the clay a left drag turns the view, a right drag turns it anywhere, a right click
// opens the menu (menuAt). During a drag the chip, 16 px below-right of the pointer: the part and its biggest bend.
// Drawn with Rectangles (the GPU's), never a Canvas repainted over the whole viewport per move; each Repeater's model
// is a count, so a drag's new numbers move the delegates there are (none made again per move).
Item {
    id: pl
    objectName: "poseLayer"
    readonly property var tool: viewport.pose
    visible: tool.on
    readonly property real dpr: Screen.devicePixelRatio
    signal menuAt(real x, real y)

    Repeater {      // the bones: a dark edge under a thin light line (readable on light clay), lit ones in the accent
        model: pl.tool.lines.length
        delegate: Item {
            required property int index
            readonly property var modelData: pl.tool.lines[index] || ({ a: [0, 0], b: [0, 0], lit: false })
            readonly property real ax: modelData.a[0] * pl.width
            readonly property real ay: modelData.a[1] * pl.height
            readonly property real dx: modelData.b[0] * pl.width - ax
            readonly property real dy: modelData.b[1] * pl.height - ay
            x: ax; y: ay
            rotation: Math.atan2(dy, dx) * 180 / Math.PI
            transformOrigin: Item.TopLeft
            Rectangle {
                width: Math.sqrt(dx * dx + dy * dy); height: 3; y: -1.5; antialiasing: true
                color: Qt.rgba(0, 0, 0, 0.35)
            }
            Rectangle {
                width: Math.sqrt(dx * dx + dy * dy); height: modelData.lit ? 2 : 1.25; y: -height / 2; antialiasing: true
                color: modelData.lit ? Theme.accent : Qt.rgba(1, 1, 1, 0.85)
            }
        }
    }
    Repeater {      // the joints: small dots
        model: pl.tool.dots.length
        delegate: Rectangle {
            required property int index
            readonly property var modelData: pl.tool.dots[index] || ({ p: [0, 0], joint: "" })
            objectName: "poseJoint_" + modelData.joint
            width: 7; height: 7; radius: 3.5; antialiasing: true
            x: modelData.p[0] * pl.width - 3.5; y: modelData.p[1] * pl.height - 3.5
            color: "white"; border.color: Qt.rgba(0, 0, 0, 0.5); border.width: 1
        }
    }
    Repeater {      // the holds: orange rings
        model: pl.tool.rings.length
        delegate: Item {
            required property int index
            readonly property var modelData: pl.tool.rings[index] || ({ p: [0, 0], bone: "" })
            objectName: "poseHold_" + modelData.bone
            width: 14; height: 14
            x: modelData.p[0] * pl.width - 7; y: modelData.p[1] * pl.height - 7
            Rectangle { anchors.fill: parent; radius: 7; color: "transparent"; border.width: 3; border.color: Qt.rgba(0, 0, 0, 0.4); antialiasing: true }
            Rectangle { anchors.fill: parent; anchors.margins: 0.5; radius: 6.5; color: "transparent"; border.width: 2; border.color: Theme.warn; antialiasing: true }
        }
    }
    Rectangle {     // the chip: the grabbed part and its biggest bend, 16 px below-right of the pointer (flipped near edges)
        objectName: "poseChip"
        visible: pl.tool.chip !== ""
        readonly property real gap: 16
        x: area.mouseX + gap + width > pl.width ? area.mouseX - gap - width : area.mouseX + gap
        y: area.mouseY + gap + height > pl.height ? area.mouseY - gap - height : area.mouseY + gap
        width: chipText.implicitWidth + 2 * Theme.gap; height: chipText.implicitHeight + Theme.grid
        radius: Theme.radiusCtl
        color: Theme.raised; border.color: Theme.popupEdge; border.width: 1
        Text {
            id: chipText
            anchors.centerIn: parent
            text: pl.tool.chip
            color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.label
            font.features: { "tnum": 1 }
        }
    }

    MouseArea {
        id: area
        objectName: "poseArea"
        anchors.fill: parent
        enabled: pl.tool.on
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        hoverEnabled: true
        preventStealing: true
        onPressed: (m) => pl.tool.press(m.x, m.y, pl.dpr, m.button === Qt.RightButton ? "right" : "left",
                                       !!(m.modifiers & Qt.AltModifier))
        onPositionChanged: (m) => { if (pressed) pl.tool.move(m.x, m.y); else pl.tool.hover(m.x, m.y, pl.dpr) }
        onReleased: (m) => pl.tool.release(m.x, m.y)
        onCanceled: pl.tool.cancel()
        onExited: pl.tool.unhover()
        CanvasCursor { kind: pl.tool.cursor }     // the arrow over the clay and around it; the turn shape while turning
    }
    Connections { target: pl.tool; function onMenuAt(x, y) { pl.menuAt(x, y) } }
}
