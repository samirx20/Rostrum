import QtQuick
import "."

// The selected item's settings: ONE generic list of InspectorRow built from the item kind's field operation
// (bridge.rows). Nothing in here knows about cameras or lights.
Panel {
    id: panel
    property var bridge
    property bool keyMarks: false        // an app with keys: rows show key marks (see InspectorRow)
    title: "Inspector"

    Text { id: name; text: panel.bridge.selectedItem.label; color: Theme.fg; font.family: uiFont
           font.pixelSize: Theme.heading; font.weight: Font.DemiBold
           anchors.left: parent.left; anchors.right: parent.right; elide: Text.ElideRight }
    Text { id: kind; text: panel.bridge.selectedItem.kind; color: Theme.fg3; font.family: uiFont
           font.pixelSize: Theme.body; font.capitalization: Font.Capitalize
           anchors.top: name.bottom; anchors.topMargin: 2 }
    Flickable {
        anchors { left: parent.left; right: parent.right; top: kind.bottom; bottom: parent.bottom }
        contentHeight: list.height; clip: true; boundsBehavior: Flickable.StopAtBounds
        Column {
            id: list
            width: parent.width
            Repeater {
                model: panel.bridge.rows
                delegate: InspectorRow { bridge: panel.bridge; keyMarks: panel.keyMarks }
            }
        }
    }
}
