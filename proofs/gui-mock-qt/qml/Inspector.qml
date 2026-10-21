import QtQuick
import "."

// The selected item's settings: ONE generic list built from the data (Doc.rowsModel); nothing is placed per control.
Panel {
    id: panel
    property var doc
    readonly property var current: doc.itemList().find(i => i.id === doc.selected)
    title: "Inspector"

    Text { id: name; text: panel.current.name; color: Theme.fg; font.pixelSize: 16; font.weight: Font.DemiBold
           anchors.left: parent.left; anchors.right: parent.right; elide: Text.ElideRight }
    Text { id: kind; text: panel.current.kind; color: Theme.fg3; font.pixelSize: Theme.body
           anchors.top: name.bottom; anchors.topMargin: 2 }
    Flickable {
        anchors { left: parent.left; right: parent.right; top: kind.bottom; bottom: parent.bottom }
        contentHeight: list.height; clip: true; boundsBehavior: Flickable.StopAtBounds
        Column {
            id: list
            width: parent.width
            Repeater {
                model: panel.doc.rowsModel
                delegate: InspectorRow { doc: panel.doc }
            }
        }
    }
}
