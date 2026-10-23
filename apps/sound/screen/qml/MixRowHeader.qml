import QtQuick
import RostrumKit

// A bus's or the master's header in the arrangement's compact rows at the bottom: its grey mark and its name
// (click selects it; the inspector shows it), its automation button (A) and, for a bus, its mute (M: bus.set mute, the
// group header's own M). Its fader is in the Mixer.
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
    NameLabel {
        x: Theme.gap + 11; width: buttons.x - x - Theme.gap; anchors.verticalCenter: parent.verticalCenter
        text: h.track.name + (h.track.kind === "bus" ? "  ·  group" : "")
        font.pixelSize: Theme.label
        color: h.track.mute ? Theme.fg3 : Theme.fg2
    }
    Row {
        id: buttons
        anchors { right: parent.right; rightMargin: Theme.grid; verticalCenter: parent.verticalCenter }
        spacing: 2
        LaneToggle { visible: h.showAuto; track: h.track }
        HeaderButton { visible: h.track.kind === "bus"; letter: "M"; lit: !!h.track.mute; litColor: Theme.warn
                       tip: "Mute this group"; onClicked: backend.toggleGroupMS(h.track.id, "mute") }
    }
}
