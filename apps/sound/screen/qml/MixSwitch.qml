import QtQuick
import RostrumKit

// A small letter button (M, S): lit in `tint` while on.
Rectangle {
    id: b
    property string text: ""
    property bool on: false
    property color tint: Theme.accent
    property bool compact: false          // a low strip: the letter button beside the name
    signal toggled(bool value)
    height: compact ? 20 : 24; radius: Theme.radiusCtl
    color: on ? tint : hover.hovered ? Theme.hover : Theme.raised
    Behavior on color { ColorAnimation { duration: Theme.fast } }
    Text { anchors.centerIn: parent; text: b.text; font.family: uiFont; font.pixelSize: b.compact ? Theme.label : Theme.body
           font.weight: Font.DemiBold; color: b.on ? Theme.app : Theme.fg2 }
    HoverHandler { id: hover; cursorShape: Qt.PointingHandCursor }
    MouseArea { anchors.fill: parent; onClicked: b.toggled(!b.on) }
}
