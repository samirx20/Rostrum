import QtQuick
import RostrumKit
import "Listening.js" as L

// The top bar's "Solo on: Strings ×" while any track or group is soloed: a solo holds every other track back from the
// play and the export, and a small green S on one header was missed for four runs. Filled in the solo colour so it
// reads from across the room; one click turns every solo off (backend.hearAll, op mix.hear_all). Absent with no solo.
Rectangle {
    id: c
    objectName: "soloChip"
    readonly property var heard: backend.listening
    readonly property string said: L.chip(heard)
    visible: said !== ""
    readonly property real limit: 260                  // longer words fold their end ("Solo on: 5 tracks" never gets there)
    readonly property real cross: x_.implicitWidth
    implicitHeight: Theme.button - 4
    implicitWidth: words.width + cross + Theme.grid + 2 * Theme.gap
    width: implicitWidth; height: implicitHeight; radius: height / 2
    color: area.containsMouse ? Qt.lighter(Theme.ok, 1.1) : Theme.ok
    Text { id: words; x: Theme.gap; anchors.verticalCenter: parent.verticalCenter; text: c.said; elide: Text.ElideRight
           width: Math.min(implicitWidth, c.limit - 2 * Theme.gap - c.cross - Theme.grid)
           color: Theme.app; font.family: uiFont; font.pixelSize: Theme.body; font.weight: Font.DemiBold }
    Text { id: x_; anchors { right: parent.right; rightMargin: Theme.gap; verticalCenter: parent.verticalCenter }
           text: "×"; color: Theme.app; font.family: uiFont; font.pixelSize: Theme.body + 2 }
    MouseArea { id: area; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: backend.hearAll("solo") }
    HoverTip { text: "Only the soloed tracks play and export. Click to hear every track again"; hovered: area.containsMouse }
}
