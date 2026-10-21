import QtQuick
import "."

// A key: a small diamond, outlined or filled. Inspector key marks and timeline keys are this one shape.
Item {
    id: k
    property bool filled: true
    property color color: Theme.fg2
    property int size: 9                   // the diamond's side before turning
    implicitWidth: Math.ceil(size * 1.42); implicitHeight: implicitWidth
    Rectangle {
        anchors.centerIn: parent
        width: k.size; height: k.size; rotation: 45; radius: 1.5
        antialiasing: true
        color: k.filled ? k.color : "transparent"
        border.width: k.filled ? 0 : 1.5; border.color: k.color
    }
}
