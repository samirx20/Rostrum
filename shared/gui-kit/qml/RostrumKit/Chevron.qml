import QtQuick
import "."

// The dropdown arrow, drawn (a font glyph like "⌄" sits low and differs per font). 8 x 5, centred in its box;
// points up while the list is open.
Item {
    id: c
    property bool open: false
    property color color: Theme.fg2
    implicitWidth: 10; implicitHeight: 10
    Canvas {
        anchors.centerIn: parent
        width: 8; height: 5
        property color ink: c.color
        onInkChanged: requestPaint()
        rotation: c.open ? 180 : 0
        Behavior on rotation { NumberAnimation { duration: Theme.fast; easing.type: Easing.OutCubic } }
        onPaint: {
            var g = getContext("2d")
            g.reset()
            g.strokeStyle = ink; g.lineWidth = 1.5; g.lineCap = "round"; g.lineJoin = "round"
            g.beginPath(); g.moveTo(0.75, 0.75); g.lineTo(4, 4.25); g.lineTo(7.25, 0.75); g.stroke()
        }
    }
}
