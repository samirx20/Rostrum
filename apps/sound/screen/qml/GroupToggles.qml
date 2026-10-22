import QtQuick
import RostrumKit

// M and S on a group's header: mute the group (bus.set mute), or solo every track in it (track.set solo), the way the
// same two buttons act on one track. Lit when on; "S" is lit when all the group's tracks are soloed.
Row {
    id: r
    property var track
    spacing: 2
    Repeater {
        model: [{ field: "mute", letter: "M", lit: Theme.warn, tip: "Mute the whole group" },
                { field: "solo", letter: "S", lit: Theme.ok, tip: "Solo every track in the group" }]
        delegate: Rectangle {
            id: t
            required property var modelData
            readonly property bool lit: !!r.track[modelData.field]
            width: 20; height: 18; radius: 4
            color: lit ? modelData.lit : tArea.containsMouse ? Theme.hover : "transparent"
            Behavior on color { ColorAnimation { duration: Theme.fast } }
            Text { anchors.centerIn: parent; text: t.modelData.letter; font.family: uiFont
                   font.pixelSize: Theme.label; font.weight: Font.DemiBold
                   color: t.lit ? Theme.app : tArea.containsMouse ? Theme.fg : Theme.fg3 }
            MouseArea { id: tArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onClicked: backend.toggleGroupMS(r.track.id, t.modelData.field) }
            HoverTip { text: t.modelData.tip; hovered: tArea.containsMouse; pressed: tArea.pressed }
        }
    }
}
