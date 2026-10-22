import QtQuick
import QtQuick.Controls as QQC
import RostrumKit

// One number for an action that asks it first (INTERACTION.md §1.2 point 5; Land a bar here: which bar). Opened by
// backend.askWanted(id, label, value); Enter or the button answers backend.landBar(id, number); Esc closes.
QQC.Popup {
    id: ask
    property string key
    property string label
    property real value
    padding: Theme.gap
    closePolicy: QQC.Popup.CloseOnEscape | QQC.Popup.CloseOnPressOutside
    onOpened: { field.text = String(value); field.forceActiveFocus(); field.selectAll() }
    background: Rectangle { color: Theme.raised; radius: Theme.radiusCtl; border.color: Theme.popupEdge }
    function go() { const v = Number(field.text); if (!isNaN(v) && field.text !== "") { close(); backend.landBar(key, v) } }
    contentItem: Row {
        spacing: Theme.gap
        Text { anchors.verticalCenter: parent.verticalCenter; text: ask.label; color: Theme.fg2
               font.family: uiFont; font.pixelSize: Theme.body }
        Rectangle {
            width: 56; height: Theme.field; radius: 4; color: Theme.sunken; border.color: Theme.accent
            TextInput { id: field; anchors.fill: parent; anchors.margins: 4; verticalAlignment: Text.AlignVCenter
                        color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body; selectByMouse: true
                        validator: IntValidator { bottom: 1; top: 999 }
                        onAccepted: ask.go() }
        }
        Button { text: "Land"; kind: "primary"; onClicked: ask.go() }
    }
}
