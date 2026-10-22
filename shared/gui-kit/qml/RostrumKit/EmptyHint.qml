import QtQuick
import "."

// An empty place's one line (INTERACTION.md 1.16): what goes here and the one way to start, with at most two buttons
// (`buttons`: [{value, label}], the first is the main one; picked(value)). The owner hides it as soon as there is
// something (visible: count === 0); it never comes back as a pop-up. Centred in its width; long lines wrap.
Column {
    id: hint
    property string text: ""
    property var buttons: []
    signal picked(string value)
    spacing: Theme.gap
    Text {
        width: hint.width; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WrapAtWordBoundaryOrAnywhere
        text: hint.text; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body
    }
    Row {
        visible: hint.buttons.length > 0
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: Theme.gap
        Repeater {
            model: hint.buttons.slice(0, 2)
            Button { required property var modelData; required property int index
                     text: modelData.label; kind: index === 0 ? "primary" : "normal"; onClicked: hint.picked(modelData.value) }
        }
    }
}
