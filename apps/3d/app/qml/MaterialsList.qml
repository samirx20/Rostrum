import QtQuick
import RostrumKit

// What the header's Materials chip opens (SPEC 6.1): the project's materials, one row each (ball, name, "N items" grey);
// a click selects the material so the settings panel shows it (edit). "+ New material" at the bottom. A row can be
// dragged onto an item in the viewport or the scene list to give it that material (MaterialGrab). Scrolls when long.
// A scripted check opens it with list.openFrom(chip).
MaterialPopup {
    id: list
    width: 280
    readonly property int ballSize: Theme.row

    natural: col.height + 2 * padding
    contentItem: Flickable {
        id: flick
        implicitHeight: Math.min(col.height, list.fit - 2 * list.padding)
        contentWidth: width; contentHeight: col.height
        clip: true; boundsBehavior: Flickable.StopAtBounds
        WheelScroll { flick: flick }   // the first click after a wheel scroll lands (the kit's WheelScroll.qml)
        Column {
            id: col
            width: flick.width
            Repeater {
                model: backend.mats.project
                delegate: Rectangle {
                    id: row
                    required property var modelData
                    objectName: "matlist:" + modelData.id
                    width: col.width; height: list.ballSize + Theme.grid; radius: Theme.radiusCtl
                    color: grab.containsMouse ? Theme.hover : "transparent"
                    Ball { id: b; x: Theme.grid; anchors.verticalCenter: parent.verticalCenter; size: list.ballSize
                           source: row.modelData.ball; colour: row.modelData.colour }
                    Text { anchors { left: b.right; leftMargin: Theme.gap; right: count.left; rightMargin: Theme.gap; verticalCenter: parent.verticalCenter }
                           text: row.modelData.label; elide: Text.ElideRight; color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body }
                    Text { id: count; anchors { right: parent.right; rightMargin: Theme.gap; verticalCenter: parent.verticalCenter }
                           text: row.modelData.users === 1 ? "1 item" : row.modelData.users + " items"
                           color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label }
                    MaterialGrab { id: grab; materialId: row.modelData.id; colour: row.modelData.colour; ball: row.modelData.ball
                                   onClicked: { list.close(); backend.mats.edit(row.modelData.id) }
                                   onDragEnded: list.close() }
                }
            }
            Rectangle {
                objectName: "matlist:new"
                width: col.width; height: Theme.popupRow + Theme.grid; radius: Theme.radiusCtl
                color: addArea.containsMouse ? Theme.hover : "transparent"
                Text { x: Theme.gap; anchors.verticalCenter: parent.verticalCenter; text: "+ New material"
                       color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body }
                MouseArea { id: addArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onClicked: { list.close(); backend.mats.newMaterial() } }
            }
        }
    }
    VScrollBar { flick: flick }
}
