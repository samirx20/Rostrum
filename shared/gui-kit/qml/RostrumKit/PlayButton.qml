import QtQuick
import "."

// Play / pause, drawn (a triangle, or two bars while playing). Click or Space: one clicked().
Rectangle {
    id: b
    property bool playing: false
    signal clicked()
    implicitWidth: Theme.button; implicitHeight: Theme.button
    radius: Theme.radiusCtl
    color: area.pressed ? Theme.active : area.containsMouse ? Theme.hover : Theme.raised
    Behavior on color { ColorAnimation { duration: Theme.fast } }
    activeFocusOnTab: true
    Keys.onSpacePressed: clicked()

    Canvas {
        anchors.centerIn: parent
        width: 10; height: 12
        property bool p: b.playing
        onPChanged: requestPaint()
        onPaint: {
            var g = getContext("2d")
            g.reset(); g.fillStyle = Theme.fg
            if (p) { g.fillRect(1, 0, 3, 12); g.fillRect(6, 0, 3, 12) }
            else { g.beginPath(); g.moveTo(1, 0); g.lineTo(10, 6); g.lineTo(1, 12); g.closePath(); g.fill() }
        }
    }
    MouseArea { id: area; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                onClicked: b.clicked() }
}
