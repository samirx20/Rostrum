import QtQuick
import RostrumKit

// A track's header in the arrangement: its colour, its name (click selects the track), and the two quick
// toggles, mute and solo (each a track.set operation; lit when on), and the round arm button for recording
// (red when armed; arming is screen state, not an edit).
Rectangle {
    id: h
    property var track
    readonly property bool on: backend.selected === track.id
    radius: Theme.radiusCtl
    color: on ? Theme.accentSoft : area.containsMouse ? Theme.raised : "transparent"
    Behavior on color { ColorAnimation { duration: Theme.fast } }

    MouseArea { id: area; anchors.fill: parent; hoverEnabled: true; onClicked: backend.select(h.track.id) }
    Rectangle { x: Theme.gap; anchors.verticalCenter: parent.verticalCenter; width: 3; radius: 1.5
                height: Math.min(parent.height - 8, 18); color: h.track.hue }
    Text {
        x: Theme.gap + 11; width: toggles.x - x - Theme.gap; anchors.verticalCenter: parent.verticalCenter
        text: h.track.name; elide: Text.ElideRight; font.family: uiFont; font.pixelSize: Theme.body
        color: h.track.mute ? Theme.fg3 : Theme.fg
    }
    Row {
        id: toggles
        anchors.right: parent.right; anchors.rightMargin: Theme.grid; anchors.verticalCenter: parent.verticalCenter
        spacing: 2
        Rectangle {
            id: arm
            readonly property bool lit: recorder.armed === h.track.id
            width: 20; height: 18; radius: 4; color: armArea.containsMouse ? Theme.hover : "transparent"
            Rectangle { anchors.centerIn: parent; width: 10; height: 10; radius: 5
                        color: arm.lit ? Theme.danger : "transparent"
                        border.width: 1.5; border.color: arm.lit ? Theme.danger : armArea.containsMouse ? Theme.fg : Theme.fg3 }
            MouseArea { id: armArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onClicked: recorder.arm(h.track.id) }
        }
        Repeater {
            model: [{ field: "mute", letter: "M", lit: Theme.warn }, { field: "solo", letter: "S", lit: Theme.ok }]
            delegate: Rectangle {
                id: t
                required property var modelData
                readonly property bool lit: h.track[modelData.field]
                width: 20; height: 18; radius: 4
                color: lit ? modelData.lit : tArea.containsMouse ? Theme.hover : "transparent"
                Behavior on color { ColorAnimation { duration: Theme.fast } }
                Text { anchors.centerIn: parent; text: t.modelData.letter; font.family: uiFont
                       font.pixelSize: Theme.label; font.weight: Font.DemiBold
                       color: t.lit ? Theme.app : tArea.containsMouse ? Theme.fg : Theme.fg3 }
                MouseArea { id: tArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onClicked: backend.toggleTrack(h.track.id, t.modelData.field) }
            }
        }
    }
}
