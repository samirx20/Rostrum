import QtQuick
import RostrumKit

// One effect in a chain, or a small pick: its name on a chip. Selected = accent; bypassed = dim (a state of the effect).
// `row`: a full-width line with the name at the left (an effect on a strip). `flat`: no fill until hovered ("+ Effect").
Rectangle {
    id: chip
    property string text: ""
    property bool selected: false
    property bool dim: false
    property bool plus: false
    property bool row: false
    property bool flat: false
    property string tip: ""             // the words under it while the pointer rests on it (what a chip that is only "+" does)
    property real maxWidth: 1e6          // the room it has: a longer name is cut with "…", never cut off by the strip
    signal clicked()
    height: 22
    width: plus ? 22 : Math.min(maxWidth, label.implicitWidth + Theme.gap * 2)
    radius: 4
    color: selected ? Theme.accentSoft : hover.hovered ? Theme.hover : flat ? "transparent" : Theme.raised
    border.width: selected ? 1 : 0; border.color: Theme.accent
    opacity: dim ? 0.45 : 1
    Behavior on color { ColorAnimation { duration: Theme.fast } }
    Text {
        id: label; text: chip.text
        x: chip.row ? Theme.gap : (chip.width - width) / 2; anchors.verticalCenter: parent.verticalCenter
        width: Math.min(implicitWidth, chip.width - Theme.gap * 2); elide: chip.row ? Text.ElideMiddle : Text.ElideRight   // a row's name: both ends show (two groups differ at the end)
        color: chip.selected ? Theme.fg : chip.plus || chip.flat ? Theme.fg2 : Theme.fg
        font.family: uiFont; font.pixelSize: chip.plus ? Theme.title : Theme.label
    }
    HoverHandler { id: hover; cursorShape: Qt.PointingHandCursor }
    HoverTip { text: chip.tip; hovered: hover.hovered }
    MouseArea { anchors.fill: parent; onClicked: chip.clicked() }
}
