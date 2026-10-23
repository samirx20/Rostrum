import QtQuick
import RostrumKit

// A small letter button (M, S, R): a raised button with an edge, filled with `tint` while on.
Rectangle {
    id: b
    property string text: ""
    property bool on: false
    property color tint: Theme.accent
    property string tip: ""
    signal toggled(bool value)
    height: 22; radius: Theme.radiusCtl
    color: on ? tint : hover.hovered ? Theme.hover : Theme.raised
    border.width: on ? 0 : 1; border.color: hover.hovered ? Theme.lineHover : Theme.line
    Behavior on color { ColorAnimation { duration: Theme.fast } }
    Text { anchors.centerIn: parent; text: b.text; font.family: uiFont; font.pixelSize: Theme.label
           font.weight: Font.DemiBold; color: b.on ? Theme.app : Theme.fg }
    HoverHandler { id: hover; cursorShape: Qt.PointingHandCursor }
    HoverTip { text: b.tip; hovered: hover.hovered }
    MouseArea { anchors.fill: parent; onClicked: b.toggled(!b.on) }
}
