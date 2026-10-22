import QtQuick
import RostrumKit

// The scanned plug-ins to choose from: `choices` is [{id, label}] (mixer.plugins.effects / .instruments);
// picking one is picked(id). While the engine is still looking, or when it found none, one line says so.
Column {
    id: list
    property var choices: []
    signal picked(string id)
    width: parent ? parent.width : 0
    Repeater {
        model: list.choices
        delegate: Rectangle {
            required property var modelData
            width: list.width; height: Theme.popupRow; radius: 4
            color: row.containsMouse ? Theme.hover : "transparent"
            NameLabel { anchors.left: parent.left; anchors.right: parent.right; anchors.leftMargin: Theme.gap - 2; anchors.rightMargin: Theme.gap - 2
                        anchors.verticalCenter: parent.verticalCenter; text: modelData.label }
            MouseArea { id: row; anchors.fill: parent; hoverEnabled: true; onClicked: list.picked(modelData.id) }
        }
    }
    Text {
        visible: list.choices.length === 0
        width: list.width; height: Theme.popupRow; leftPadding: Theme.gap - 2; verticalAlignment: Text.AlignVCenter
        text: mixer.plugins.busy ? "Looking for plug-ins…" : "No plug-ins found"
        color: Theme.fg3; font.pixelSize: Theme.body; font.family: uiFont
    }
}
