import QtQuick
import RostrumKit

// One effect in a chain: its name as a small chip. Selected = accent; bypassed = dim (a state of the effect).
Rectangle {
    id: chip
    property string text: ""
    property bool selected: false
    property bool dim: false
    property bool plus: false
    property string tip: ""             // the words under it while the pointer rests on it (what a chip that is only "+" does)
    property real maxWidth: 1e6          // the room it has: a longer name is cut with "…", never cut off by the strip
    signal clicked()
    height: 22
    width: plus ? 22 : Math.min(maxWidth, label.implicitWidth + Theme.gap * 2)
    radius: 4
    color: selected ? Theme.accentSoft : hover.hovered ? Theme.hover : Theme.raised
    border.width: selected ? 1 : 0; border.color: Theme.accent
    opacity: dim ? 0.45 : 1
    Behavior on color { ColorAnimation { duration: Theme.fast } }
    Text {
        id: label; anchors.centerIn: parent; text: chip.text
        width: Math.min(implicitWidth, chip.width - Theme.gap * 2); elide: Text.ElideRight
        color: chip.selected ? Theme.fg : chip.plus ? Theme.fg2 : Theme.fg
        font.family: uiFont; font.pixelSize: chip.plus ? Theme.title : Theme.label
    }
    HoverHandler { id: hover; cursorShape: Qt.PointingHandCursor }
    HoverTip { text: chip.tip; hovered: hover.hovered }
    MouseArea { anchors.fill: parent; onClicked: chip.clicked() }
}
