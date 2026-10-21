import QtQuick
import "."

// On/off switch.
Rectangle {
    id: sw
    property bool checked: false
    signal toggled(bool value)
    implicitWidth: 32; implicitHeight: 18; radius: 9
    color: checked ? Theme.accent : Theme.active
    Behavior on color { ColorAnimation { duration: Theme.fast } }
    Rectangle {
        y: 2; width: 14; height: 14; radius: 7; color: "white"
        x: sw.checked ? sw.width - width - 2 : 2
        Behavior on x { NumberAnimation { duration: Theme.fast; easing.type: Easing.OutCubic } }
    }
    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: sw.toggled(!sw.checked) }
}
