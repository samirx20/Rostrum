import QtQuick
import RostrumKit

// One small button on a track's, group's or bus's header (R, M, S, A), the way a mixing desk draws them: a raised
// key with a thin edge that reads as a button at rest, filled with its colour when on. `clicked` does the work.
Rectangle {
    id: b
    property string letter
    property bool lit: false
    property color litColor: Theme.accent
    property bool soft: false           // lit as a tint with an edge (an open lane), not a solid fill
    property string tip: ""
    property bool dot: false            // a small dot in the corner: something is there (automation written)
    property color dotColor: Theme.fg3
    signal clicked()
    width: 20; height: 20; radius: 4
    color: lit ? (soft ? Theme.accentSoft : litColor) : area.containsMouse ? Theme.hover : Theme.raised
    border.width: 1
    border.color: lit ? litColor : area.containsMouse ? Theme.lineHover : Theme.line
    Behavior on color { ColorAnimation { duration: Theme.fast } }
    Text {
        anchors.centerIn: parent; text: b.letter; font.family: uiFont
        font.pixelSize: Theme.label; font.weight: Font.DemiBold
        color: b.lit && !b.soft ? Theme.app : b.lit || area.containsMouse ? Theme.fg : Theme.fg2
    }
    Rectangle { visible: b.dot; x: parent.width - 6; y: 2; width: 4; height: 4; radius: 2; color: b.dotColor }
    MouseArea { id: area; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                onClicked: b.clicked() }
    HoverTip { text: b.tip; hovered: area.containsMouse && b.tip !== ""; pressed: area.pressed }
}
