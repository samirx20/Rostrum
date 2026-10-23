import QtQuick
import "."

// The look of every menu and popup: the one edge (Theme.popupEdge, 1 px) and a soft drop shadow, as Figma's menus have.
// `background: MenuBackground { }`. The shadow is a few faint rounded layers, a little lower than high, so there is no effect module.
Item {
    property real radius: Theme.radiusCtl
    Repeater {
        model: 5
        Rectangle {
            required property int index
            anchors { fill: parent; margins: -(index + 1) * 2; topMargin: -(index + 1) * 2 + 3; bottomMargin: -(index + 1) * 2 - 3 }
            radius: parent.radius + (index + 1) * 2
            color: Qt.rgba(0, 0, 0, 0.09)
        }
    }
    Rectangle { anchors.fill: parent; color: Theme.raised; radius: parent.radius; border.color: Theme.popupEdge }
}
