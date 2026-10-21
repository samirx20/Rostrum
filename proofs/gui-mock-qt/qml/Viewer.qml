import QtQuick
import "."

// Stand-in viewport: a dark rectangle with the selected item's name and kind, muted.
Panel {
    id: panel
    property var doc
    readonly property var current: doc.itemList().find(i => i.id === doc.selected)
    title: "Viewer"
    Rectangle {
        anchors.fill: parent; color: "#0d0d0d"; radius: Theme.radiusCtl
        Column {
            anchors.centerIn: parent; spacing: 4
            Text { anchors.horizontalCenter: parent.horizontalCenter; text: panel.current.name; color: Theme.fg3
                   font.pixelSize: 20; font.weight: Font.DemiBold }
            Text { anchors.horizontalCenter: parent.horizontalCenter; text: panel.current.kind; color: "#5c5c5c"; font.pixelSize: Theme.body }
        }
    }
}
