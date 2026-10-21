import QtQuick
import "."

// A button: "normal" (raised), "primary" (accent) or "ghost" (no box until hovered). Optional key hint at the
// right ("Ctrl K"). `danger` colours the text red (delete, discard). Click, Space or Enter: one clicked().
Item {
    id: b
    property string text: ""
    property string kind: "normal"
    property string hint: ""
    property bool danger: false
    property bool down: false            // shown pressed (e.g. a panel that is open)
    readonly property bool hovered: hoverHandler.hovered
    signal clicked()
    implicitHeight: Theme.button
    implicitWidth: label.implicitWidth + (hint ? hintBox.width + Theme.gap : 0) + 2 * Theme.pad
    activeFocusOnTab: true
    Keys.onSpacePressed: clicked()
    Keys.onReturnPressed: clicked()

    HoverHandler { id: hoverHandler; cursorShape: Qt.PointingHandCursor }
    Rectangle {
        anchors.fill: parent; radius: Theme.radiusCtl
        color: b.kind === "primary" ? (b.hovered || area.pressed ? Theme.accentHover : Theme.accent)
             : area.pressed || b.down ? Theme.active
             : b.hovered ? Theme.hover
             : b.kind === "ghost" ? "transparent" : Theme.raised
        border.width: b.activeFocus ? 1 : 0; border.color: b.kind === "primary" ? "white" : Theme.accent
        Behavior on color { ColorAnimation { duration: Theme.fast } }
    }
    Text {
        id: label
        anchors.left: parent.left; anchors.leftMargin: Theme.pad
        anchors.verticalCenter: parent.verticalCenter
        text: b.text; font.pixelSize: Theme.body; font.family: uiFont
        font.weight: b.kind === "primary" ? Font.DemiBold : Font.Normal
        color: b.kind === "primary" ? "white" : b.danger ? Theme.danger : Theme.fg
    }
    KeyHint { id: hintBox; visible: b.hint !== ""; text: b.hint
              anchors.right: parent.right; anchors.rightMargin: Theme.grid; anchors.verticalCenter: parent.verticalCenter }
    MouseArea { id: area; anchors.fill: parent; onClicked: b.clicked() }
}
