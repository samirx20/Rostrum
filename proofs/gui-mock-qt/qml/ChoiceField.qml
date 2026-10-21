import QtQuick
import QtQuick.Controls
import "."

// A choice: segmented control for up to three options, a dropdown for more.
Item {
    id: f
    property var options: []
    property string current: ""
    signal picked(string value)
    implicitHeight: 24; implicitWidth: 160
    readonly property bool segmented: options.length <= 3

    Row {  // segmented
        visible: f.segmented; anchors.fill: parent; spacing: 2
        Repeater {
            model: f.segmented ? f.options : []
            delegate: Rectangle {
                required property string modelData
                width: (f.width - 2 * (f.options.length - 1)) / f.options.length; height: f.height; radius: Theme.radiusCtl
                color: modelData === f.current ? Theme.accentSoft : seg.containsMouse ? Theme.hover : Theme.raised
                Behavior on color { ColorAnimation { duration: Theme.fast } }
                Text { anchors.centerIn: parent; text: modelData; font.pixelSize: Theme.body
                       color: modelData === f.current ? Theme.fg : Theme.fg2 }
                MouseArea { id: seg; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onClicked: f.picked(modelData) }
            }
        }
    }
    Rectangle {  // dropdown button
        visible: !f.segmented; anchors.fill: parent; radius: Theme.radiusCtl
        color: btn.containsMouse ? Theme.hover : Theme.raised
        Text { anchors.left: parent.left; anchors.leftMargin: Theme.gap; anchors.right: chev.left; anchors.verticalCenter: parent.verticalCenter
               text: f.current; color: Theme.fg; font.pixelSize: Theme.body; elide: Text.ElideRight }
        Text { id: chev; anchors.right: parent.right; anchors.rightMargin: Theme.gap; anchors.verticalCenter: parent.verticalCenter
               text: "⌄"; color: Theme.fg2; font.pixelSize: Theme.body }
        MouseArea { id: btn; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: menu.open() }
    }
    Popup {
        id: menu
        y: f.height + 2; width: f.width; padding: 4
        background: Rectangle { color: Theme.raised; radius: Theme.radiusCtl; border.color: Qt.rgba(1, 1, 1, 0.08) }
        Column {
            width: parent.width
            Repeater {
                model: f.options
                delegate: Rectangle {
                    required property string modelData
                    width: parent.width; height: Theme.row; radius: 4
                    color: modelData === f.current ? Theme.accentSoft : opt.containsMouse ? Theme.hover : "transparent"
                    Text { anchors.left: parent.left; anchors.leftMargin: Theme.gap; anchors.verticalCenter: parent.verticalCenter
                           text: modelData; color: Theme.fg; font.pixelSize: Theme.body }
                    MouseArea { id: opt; anchors.fill: parent; hoverEnabled: true
                                onClicked: { menu.close(); f.picked(modelData) } }
                }
            }
        }
    }
}
