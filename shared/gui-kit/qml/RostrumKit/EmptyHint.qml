import QtQuick
import "."

// An empty place's one line (INTERACTION.md 1.16): what goes here and the one way to start, with at most two buttons
// (`buttons`: [{value, label}], the first is the main one; picked(value)). The owner hides it as soon as there is
// something (visible: count === 0); it never comes back as a pop-up. Centred in its width; long lines wrap.
Column {
    id: emptyHint
    property string text: ""
    property var buttons: []
    signal picked(string value)
    spacing: Theme.gap
    Text {
        width: emptyHint.width; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WrapAtWordBoundaryOrAnywhere
        text: emptyHint.text; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body
    }
    Row {
        visible: emptyHint.buttons.length > 0
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: Theme.gap
        Repeater {
            model: emptyHint.buttons.slice(0, 2)
            Button { required property var modelData; required property int index
                     text: modelData.label; kind: index === 0 ? "primary" : "normal"; onClicked: emptyHint.picked(modelData.value) }
        }
    }
}
