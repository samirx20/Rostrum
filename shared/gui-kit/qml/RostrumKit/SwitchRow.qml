import QtQuick
import "."

// One switch line: the label in the label column, then the switch. The words are part of the switch: clicking
// them flips it too (the one place for that; settings rows, the paint panel and any app's switch line use it).
// `label` / `labelColumn` / `checked`; toggled(value) once per flip. The line's own height is the caller's.
Item {
    id: r
    property string label
    property int labelColumn: 100
    property alias checked: sw.checked
    property alias switchName: sw.objectName
    signal toggled(bool value)
    width: parent ? parent.width : 0
    height: Theme.row

    Text {
        id: words
        width: r.labelColumn - Theme.gap; anchors.verticalCenter: parent.verticalCenter
        text: r.label; color: sw.hovered || wordsArea.containsMouse ? Theme.fg : Theme.fg2
        font.pixelSize: Theme.body; font.family: uiFont; elide: Text.ElideRight
        MouseArea {
            id: wordsArea
            anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
            onClicked: r.toggled(!sw.checked)
        }
    }
    Toggle { id: sw; x: r.labelColumn; anchors.verticalCenter: parent.verticalCenter; onToggled: (v) => r.toggled(v) }
}
