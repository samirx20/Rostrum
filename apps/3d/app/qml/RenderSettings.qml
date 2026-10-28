import QtQuick
import RostrumKit

// The Render page's settings panel with nothing selected (SPEC §11.3): the shown shot's render settings (the sheet's
// rows: Quality and Size saved on the shot, Save as; ExportSettings3D.qml), its measured time (RenderEstimate.qml),
// then Render (this shot next, F12) and Add to queue (after the others). Both are render.queue.add (queue.py).
Panel {
    id: panel
    readonly property var q: backend.renderQueue
    readonly property string shot: backend.shotInfo.id

    Item {
        anchors { fill: parent; rightMargin: Theme.padRight - panel.bodyPad }
        Text {
            id: head
            anchors { left: parent.left; right: parent.right }
            text: backend.shotInfo.label; color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.heading
            font.weight: Font.DemiBold; elide: Text.ElideRight
        }
        Text {
            id: sub
            anchors { left: parent.left; right: parent.right; top: head.bottom; topMargin: 2 }
            text: "Shot · render settings"; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.body
        }
        Flickable {
            id: flick
            anchors { left: parent.left; right: parent.right; top: sub.bottom; bottom: parent.bottom; topMargin: Theme.groupGap }
            contentHeight: col.height; clip: true; boundsBehavior: Flickable.StopAtBounds
            WheelScroll { flick: flick }   // the first click after a wheel scroll lands (the kit's WheelScroll.qml)
            Column {
                id: col
                width: parent.width
                spacing: Theme.gap
                ExportSettings3D { }
                RenderEstimate { }
                Row {
                    spacing: Theme.gap
                    Button { text: "Render"; hint: "F12"; kind: "primary"; onClicked: panel.q.renderNext(panel.shot) }
                    Button { text: "Add to queue"; onClicked: panel.q.add(panel.shot) }
                }
            }
        }
    }
}
