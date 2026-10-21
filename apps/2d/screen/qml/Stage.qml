import QtQuick
import RostrumKit

// The canvas: the engine's frame at the playhead (image://frame, rendered off the GUI thread), fitted on a
// neutral backdrop, with the selected layer's box. Press on a layer selects it; dragging moves it
// (backend.beginMove / moveBy / endDrag: one gesture = one undo step; an animated x / y gets a key at the playhead).
Panel {
    id: panel
    title: "Canvas"
    readonly property var info: backend.frameInfo
    headerRight: Text { text: panel.info.width + " × " + panel.info.height + "  ·  " + panel.info.fps + " fps"
                        color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label }

    Rectangle {
        id: well
        anchors.fill: parent
        radius: Theme.radiusCtl; color: Theme.sunken
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
            Rectangle {  // the frame's edge, so a dark composition still shows where it ends
                anchors.fill: parent; anchors.margins: -1
                color: "transparent"; border.width: 1; border.color: Theme.popupEdge
            }
            Rectangle {  // the selected layer
                readonly property var b: backend.selBox
                visible: b.w !== undefined
                x: (b.x || 0) * well.fit - 1; y: (b.y || 0) * well.fit - 1
                width: (b.w || 0) * well.fit + 2; height: (b.h || 0) * well.fit + 2
                color: "transparent"; border.width: 1; border.color: Theme.accent
                Repeater {
                    model: 4
                    delegate: Rectangle {
                        required property int index
                        width: 7; height: 7; color: "white"; border.width: 1; border.color: Theme.accent
                        x: (index % 2) * parent.width - 3.5; y: Math.floor(index / 2) * parent.height - 3.5
                    }
                }
            }
        }
        MouseArea {
            anchors.fill: parent
            preventStealing: true
            property bool moving: false
            property real sx: 0
            property real sy: 0
            function comp(m) { return Qt.point((m.x - frame.x) / well.fit, (m.y - frame.y) / well.fit) }
            onPressed: (m) => {
                var p = comp(m)
                moving = backend.pickAt(p.x, p.y) !== "" && backend.beginMove()
                sx = m.x; sy = m.y
            }
            onPositionChanged: (m) => { if (moving) backend.moveBy((m.x - sx) / well.fit, (m.y - sy) / well.fit) }
            onReleased: { if (moving) backend.endDrag(); moving = false }
            onCanceled: { if (moving) backend.endDrag(); moving = false }
        }
    }
}
