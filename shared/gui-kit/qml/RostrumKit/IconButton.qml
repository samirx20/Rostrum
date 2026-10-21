import QtQuick
import "."

// A small square button with a glyph (a short text such as "+", "×", "⋯" or a drawn mark passed as `icon`).
// Same hover and press as Button; `kind`: "normal" (raised) or "ghost" (no box until hovered); `danger` colours the
// glyph red. Click, Space or Enter: one clicked().
Item {
    id: b
    property string glyph: ""
    property string kind: "normal"
    property bool danger: false
    property bool down: false            // shown pressed (e.g. a toggled-on tool)
    property string tip: ""              // what it does, in words: shown under it while the pointer rests on it
    readonly property bool hovered: hoverHandler.hovered
    signal clicked()
    implicitWidth: Theme.button; implicitHeight: Theme.button
    activeFocusOnTab: true
    Keys.onSpacePressed: clicked()
    Keys.onReturnPressed: clicked()

    HoverHandler { id: hoverHandler; cursorShape: Qt.PointingHandCursor }
    Rectangle {
        anchors.fill: parent; radius: Theme.radiusCtl
        color: area.pressed || b.down ? Theme.active : b.hovered ? Theme.hover : b.kind === "ghost" ? "transparent" : Theme.raised
        border.width: b.activeFocus ? 1 : 0; border.color: Theme.accent
        Behavior on color { ColorAnimation { duration: Theme.fast } }
    }
    Text {
        anchors.centerIn: parent
        text: b.glyph; font.pixelSize: Theme.heading; font.family: uiFont
        color: b.danger ? Theme.danger : b.hovered || b.down ? Theme.fg : Theme.fg2
    }
    MouseArea { id: area; anchors.fill: parent; onClicked: b.clicked() }
    HoverTip { text: b.tip; hovered: b.hovered; pressed: area.pressed || b.down }
}
