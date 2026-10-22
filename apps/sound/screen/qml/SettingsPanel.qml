import QtQuick
import QtQuick.Controls as QQC
import RostrumKit

// Settings (screensound/settings_page.py, `settingsPage`): the kit's own Inspector on the settings' field data, so
// it shows only what applies now, most important first; a change is saved at once. Under it: where the models and
// projects are and how much room the models take, and the last save's word.
QQC.Popup {
    id: pop
    parent: QQC.Overlay.overlay
    anchors.centerIn: parent
    width: 440; height: Math.min(parent.height - 80, 600); padding: 0
    modal: true; closePolicy: QQC.Popup.CloseOnEscape | QQC.Popup.CloseOnPressOutside
    QQC.Overlay.modal: Rectangle { color: Theme.scrim }
    onAboutToShow: settingsPage.reload()
    background: Rectangle { color: Theme.panel; radius: Theme.radiusPanel; border.color: Theme.popupEdge }
    contentItem: Item {
        Inspector {
            anchors { left: parent.left; right: parent.right; top: parent.top; bottom: foot.top }
            title: "Settings"; bridge: settingsPage
        }
        Column {
            id: foot
            anchors { left: parent.left; right: parent.right; bottom: parent.bottom; margins: Theme.pad }
            spacing: Theme.gap
            Text { width: parent.width; wrapMode: Text.WordWrap; text: settingsPage.facts; color: Theme.fg3
                   font.family: uiFont; font.pixelSize: Theme.label; lineHeight: 1.3 }
            Text { visible: text !== ""; width: parent.width; wrapMode: Text.WordWrap; text: settingsPage.status
                   color: text.indexOf("Error") === 0 ? Theme.danger : Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body }
            Button { anchors.right: parent.right; text: "Done"; kind: "primary"; onClicked: pop.close() }
        }
    }
}
