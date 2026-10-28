import QtQuick
import RostrumKit

// The material picker (SPEC 6.2): two clicks from the Material row's swatch to a material. "This project": one row per
// material (ball, name, "Used by N" grey at the right); a click gives it to the selection. "Start from": a grid of balls
// with their labels, three to a row; a click makes a new material from that start and gives it to the selection.
// A project material's row can also be dragged onto an item (MaterialGrab). It is 300 px wide (the settings panel's
// width) and scrolls when the window is short. A scripted check opens it with picker.openFrom(anchor).
MaterialPopup {
    id: picker
    width: 300
    property bool faces: false        // Edit mesh: the picked faces take the material (meshEdit), not the selected item
    function give(id) { picker.close(); faces ? meshEdit.setFaceMaterial(id) : backend.mats.assign(id) }
    readonly property int tile: (width - 2 * padding) / 3     // three across: "Polished metal" reads whole
    readonly property int ballSize: Theme.row
    readonly property int tileHeight: ballSize + Theme.rowDense + Theme.gap

    natural: col.height + 2 * padding
    contentItem: Flickable {
        id: flick
        objectName: "materialPickerScroll"
        // when it scrolls, it ends at a whole row of starting points (or above "Start from" when none fits), so no
        // label shows as a sliver at the bottom
        readonly property real room: picker.fit - 2 * picker.padding
        readonly property real tileRows: Math.floor((room - starts.y) / picker.tileHeight)
        implicitHeight: col.height <= room ? col.height
                        : tileRows >= 1 ? starts.y + tileRows * picker.tileHeight
                        : starts.y - Theme.rowDense > Theme.rowDense ? starts.y - Theme.rowDense : room
        contentWidth: width; contentHeight: col.height
        clip: true; boundsBehavior: Flickable.StopAtBounds
        Column {
            id: col
            width: flick.width
            Rectangle {   // faces only: back to the shape's own material
                visible: picker.faces
                width: col.width; height: visible ? picker.ballSize + Theme.grid : 0; radius: Theme.radiusCtl
                color: noneArea.containsMouse ? Theme.hover : "transparent"
                Text { x: Theme.grid; anchors.verticalCenter: parent.verticalCenter; text: "The shape's own"
                       color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body }
                MouseArea { id: noneArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onClicked: picker.give("") }
            }
            Text { visible: backend.mats.project.length > 0; height: visible ? Theme.rowDense : 0; verticalAlignment: Text.AlignVCenter
                   text: "This project"; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label; font.weight: Font.DemiBold }
            Repeater {
                model: backend.mats.project
                delegate: Rectangle {
                    id: row
                    required property var modelData
                    objectName: "matpick:" + modelData.id
                    width: col.width; height: picker.ballSize + Theme.grid; radius: Theme.radiusCtl
                    color: grab.containsMouse ? Theme.hover : "transparent"
                    Ball { id: b; x: Theme.grid; anchors.verticalCenter: parent.verticalCenter; size: picker.ballSize
                           source: row.modelData.ball; colour: row.modelData.colour
                           selected: row.modelData.id === backend.mats.current.id }
                    Text { anchors { left: b.right; leftMargin: Theme.gap; right: users.left; rightMargin: Theme.gap; verticalCenter: parent.verticalCenter }
                           text: row.modelData.label; elide: Text.ElideRight; color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body }
                    Text { id: users; anchors { right: parent.right; rightMargin: Theme.gap; verticalCenter: parent.verticalCenter }
                           text: "Used by " + row.modelData.users; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label }
                    MaterialGrab { id: grab; materialId: row.modelData.id; colour: row.modelData.colour; ball: row.modelData.ball
                                   onClicked: picker.give(row.modelData.id)
                                   onDragEnded: picker.close() }
                }
            }
            Item { width: 1; height: Theme.gap; visible: backend.mats.project.length > 0 && !picker.faces }
            Text { visible: !picker.faces; height: picker.faces ? 0 : Theme.rowDense; verticalAlignment: Text.AlignVCenter
                   text: "Start from"; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label; font.weight: Font.DemiBold }
            Flow {
                id: starts
                width: col.width; visible: !picker.faces; height: picker.faces ? 0 : implicitHeight
                Repeater {
                    model: backend.mats.starts
                    delegate: Rectangle {
                        id: tile
                        required property var modelData
                        objectName: "matstart:" + modelData.value
                        width: picker.tile; height: picker.tileHeight; radius: Theme.radiusCtl
                        color: tgrab.containsMouse ? Theme.hover : "transparent"
                        Ball { id: tb; anchors.horizontalCenter: parent.horizontalCenter; y: Theme.gap; size: picker.ballSize
                               source: tile.modelData.ball; colour: tile.modelData.colour }
                        Text { anchors { top: tb.bottom; topMargin: Theme.grid; left: parent.left; right: parent.right }
                               horizontalAlignment: Text.AlignHCenter; elide: Text.ElideRight
                               text: tile.modelData.label; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.label }
                        MaterialGrab { id: tgrab; onClicked: { picker.close(); backend.mats.startFrom(tile.modelData.value) } }
                    }
                }
            }
        }
    }
    VScrollBar { flick: flick }
}
