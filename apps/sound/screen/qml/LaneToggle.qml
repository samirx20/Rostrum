import QtQuick
import RostrumKit

// A track row's small "Auto" chip, at the right end of its lane: opens and closes the automation lane under the
// row (volume, pan, a send's level …). A dot says the track already holds automation; lit while the lane is open.
Rectangle {
    id: t
    property var track
    readonly property bool open: !!track.auto
    width: label.implicitWidth + (track.autoUsed ? 20 : 12); height: Math.min(16, parent.height - 4)
    radius: 4
    color: open ? Theme.accentSoft : area.containsMouse ? Theme.hover : Theme.raised
    border.width: open ? 1 : 0; border.color: Theme.accent
    opacity: open || area.containsMouse ? 1 : 0.8
    Row {
        anchors.centerIn: parent; spacing: 4
        Rectangle { visible: t.track.autoUsed; width: 5; height: 5; radius: 2.5; anchors.verticalCenter: parent.verticalCenter
                    color: t.track.hue }
        Text { id: label; text: "Auto"; color: t.open ? Theme.fg : Theme.fg2; font.family: uiFont; font.pixelSize: Theme.label - 1 }
    }
    MouseArea { id: area; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                onClicked: backend.toggleLanes(t.track.id) }
}
