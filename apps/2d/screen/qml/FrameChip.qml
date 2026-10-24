import QtQuick
import RostrumKit

// "‹ Frame": the frame is entirely out of view (WorldFrame.qml says which way). A small chip on that edge of the well;
// a click fits the view to the frame, like Ctrl+0. It never moves the view by itself. Above the canvas's mouse area.
Rectangle {
    id: chip
    required property var world
    signal clicked()
    readonly property string edge: world.edge
    readonly property var arrows: ({ left: "‹ Frame", right: "Frame ›", top: "↑ Frame", bottom: "↓ Frame" })
    visible: !backend.playing && edge !== ""
    width: words.width + 2 * Theme.gap + 4; height: words.height + 8
    radius: height / 2; color: mouse.containsMouse ? Theme.lineHover : Theme.raised
    x: edge === "left" ? Theme.gap : edge === "right" ? parent.width - width - Theme.gap
       : Math.max(Theme.gap, Math.min(parent.width - width - Theme.gap, world.along - width / 2))
    y: edge === "top" ? Theme.gap : edge === "bottom" ? parent.height - height - Theme.gap
       : Math.max(Theme.gap, Math.min(parent.height - height - Theme.gap, world.along - height / 2))
    Text { id: words; anchors.centerIn: parent; text: chip.arrows[chip.edge] || ""; color: Theme.fg
           font.family: uiFont; font.pixelSize: Theme.label }
    MouseArea { id: mouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: chip.clicked() }
}
