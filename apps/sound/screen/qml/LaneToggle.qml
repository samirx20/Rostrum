import QtQuick
import RostrumKit

// A track row's small "Auto" chip, in its header beside Rec / M / S (never over the notes): opens and closes the automation lane under the
// row (volume, pan, a send's level …). A dot says the track already holds automation; lit while the lane is open.
Rectangle {
    id: t
    property var track
    readonly property bool open: !!track.auto
    width: label.implicitWidth + (track.autoUsed ? 20 : 12); height: 18
    radius: 4
    color: open ? Theme.accentSoft : area.containsMouse ? Theme.hover : "transparent"
    border.width: open ? 1 : 0; border.color: Theme.accent
    Row {
        anchors.centerIn: parent; spacing: 4
        Rectangle { visible: t.track.autoUsed; width: 5; height: 5; radius: 2.5; anchors.verticalCenter: parent.verticalCenter
                    color: t.track.hue }
        Text { id: label; text: "Auto"; color: t.open ? Theme.fg : area.containsMouse ? Theme.fg : Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label - 1 }
    }
    MouseArea { id: area; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                onClicked: backend.toggleLanes(t.track.id) }
    HoverTip { text: t.open ? "Close the automation lane" : "Automation: draw volume, pan and more changing over time"
               hovered: area.containsMouse; pressed: area.pressed }
}
