import QtQuick
import RostrumKit

// A round material preview. Shows the rendered `ball` picture when there is one (a round render on a clear ground);
// while it is still rendering ("") it is a flat circle of the material's base `colour`, so nothing is ever blank.
// `selected` draws a ring in the accent just outside it.
Item {
    id: ball
    property url source: ""            // the rendered ball ("" while it renders)
    property color colour: Theme.raised
    property bool selected: false
    property int size: Theme.field
    implicitWidth: size; implicitHeight: size

    Rectangle {     // the flat stand-in, under the picture (covered once it is ready)
        anchors.fill: parent; radius: width / 2; color: ball.colour
        border.width: 1; border.color: Theme.popupEdge
        visible: picture.status !== Image.Ready
    }
    Image {
        id: picture
        anchors.fill: parent; asynchronous: false; smooth: true     // image://ball: made ahead, a lookup (rostrum_gui/screen_images.py)
        source: ball.source; sourceSize: Qt.size(ball.size * 2, ball.size * 2); fillMode: Image.PreserveAspectFit
    }
    Rectangle {     // the selected ring
        anchors.fill: parent; anchors.margins: -2; radius: width / 2; color: "transparent"
        border.width: 2; border.color: Theme.accent; visible: ball.selected
    }
}
