import QtQuick
import RostrumKit

// A bus's or the master's header in the arrangement's compact rows at the bottom: its grey mark and its name
// (click selects it; the inspector shows it). Its mute and fader are in the Mixer; here it only carries lanes.
Rectangle {
    id: h
    property var track
    property bool showAuto: true
    readonly property bool on: backend.selected === track.id
    radius: Theme.radiusCtl
    color: on ? Theme.accentSoft : area.containsMouse ? Theme.raised : "transparent"

    HoverHandler { id: hover }   // kept while the pointer is on the Auto chip itself
    MouseArea { id: area; anchors.fill: parent; hoverEnabled: true; onClicked: backend.select(h.track.id) }
    Rectangle { x: Theme.gap; anchors.verticalCenter: parent.verticalCenter; width: 3; radius: 1.5
                height: Math.min(parent.height - 6, 14); color: h.track.hue }
    NameLabel {
        x: Theme.gap + 11; width: autoChip.x - x - Theme.gap; anchors.verticalCenter: parent.verticalCenter
        text: h.track.name + (h.track.kind === "bus" ? "  ·  group" : "")
        font.pixelSize: Theme.label
        color: h.track.mute ? Theme.fg3 : Theme.fg2
    }
    LaneToggle { id: autoChip; visible: h.showAuto && (hover.hovered || h.track.autoUsed || !!h.track.auto); track: h.track   // on hover or in use
                 anchors { right: parent.right; rightMargin: Theme.grid; verticalCenter: parent.verticalCenter } }
}
