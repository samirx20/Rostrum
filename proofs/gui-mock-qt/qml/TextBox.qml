import QtQuick
import "."

// A one-line text field.
Rectangle {
    id: f
    property string text: ""
    signal edited(string value)
    implicitHeight: 24; implicitWidth: 160; radius: Theme.radiusCtl
    color: Theme.raised
    border.width: input.activeFocus ? 1 : 0; border.color: Theme.accent
    TextInput {
        id: input
        anchors.fill: parent; anchors.leftMargin: Theme.gap; anchors.rightMargin: Theme.gap; verticalAlignment: TextInput.AlignVCenter
        text: f.text; color: Theme.fg; font.pixelSize: Theme.body; selectionColor: Theme.accent; clip: true
        onTextEdited: f.edited(text)
    }
}
