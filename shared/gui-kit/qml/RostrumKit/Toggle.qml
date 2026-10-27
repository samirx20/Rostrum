import QtQuick
import "."

// On / off switch. Click or Space flips it: one toggled(value).
Item {
    id: t
    property bool checked: false
    readonly property bool hovered: hoverHandler.hovered
    signal toggled(bool value)
    implicitWidth: 32; implicitHeight: Theme.field
    activeFocusOnTab: true
    Keys.onSpacePressed: { if (typeof ack !== "undefined" && ack) ack.by(t); t.toggled(!t.checked) }

    HoverHandler { id: hoverHandler; cursorShape: Qt.PointingHandCursor }
    Rectangle {
        id: track
        anchors.verticalCenter: parent.verticalCenter
        width: 32; height: 18; radius: 9
        color: t.checked ? (t.hovered ? Theme.accentHover : Theme.accent) : (t.hovered ? Theme.lineHover : Theme.active)
        border.width: t.activeFocus ? 1 : 0; border.color: Theme.fg2
        Rectangle {     // on / off is a pick: drawn at once, colour and knob alike (INTERACTION principle 10)
            y: 2; width: 14; height: 14; radius: 7; color: "white"
            x: t.checked ? track.width - width - 2 : 2
        }
    }
    MouseArea { anchors.fill: parent; onClicked: { if (typeof ack !== "undefined" && ack) ack.by(t); t.toggled(!t.checked) } }
}
