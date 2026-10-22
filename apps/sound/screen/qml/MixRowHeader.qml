import QtQuick
import RostrumKit

// A bus's or the master's header in the arrangement's compact rows at the bottom: its grey mark and its name
// (click selects it; the inspector shows it). Its mute and fader are on the Mix page; here it only carries lanes.
Rectangle {
    id: h
    property var track
    property bool showAuto: true
    readonly property bool on: backend.selected === track.id
    radius: Theme.radiusCtl
    color: on ? Theme.accentSoft : area.containsMouse ? Theme.raised : "transparent"

    MouseArea { id: area; anchors.fill: parent; hoverEnabled: true; onClicked: backend.select(h.track.id) }
    Rectangle { x: Theme.gap; anchors.verticalCenter: parent.verticalCenter; width: 3; radius: 1.5
                height: Math.min(parent.height - 6, 14); color: h.track.hue }
    Text {
        x: Theme.gap + 11; width: autoChip.x - x - Theme.gap; anchors.verticalCenter: parent.verticalCenter
        text: h.track.name + (h.track.kind === "bus" ? "  ·  bus" : "")
        elide: Text.ElideRight; font.family: uiFont; font.pixelSize: Theme.label
        color: h.track.mute ? Theme.fg3 : Theme.fg2
    }
    LaneToggle { id: autoChip; visible: h.showAuto; track: h.track
                 anchors { right: parent.right; rightMargin: Theme.grid; verticalCenter: parent.verticalCenter } }
}
