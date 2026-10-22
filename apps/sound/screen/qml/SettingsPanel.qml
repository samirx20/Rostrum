import QtQuick
import QtQuick.Controls as QQC
import RostrumKit

// Preferences (screensound/settings_page.py, `settingsPage`): the kit's own Inspector on the settings' field data, so
// it shows only what applies now, most important first; a change is saved at once. Under it: where the models and
// projects are and how much room the models take, and the last save's word.
QQC.Popup {
    id: pop
    parent: QQC.Overlay.overlay
    anchors.centerIn: parent
    width: 440; padding: 0
    // as tall as its rows need (no empty band under More), up to what the window leaves
    property real rowsHeight: 0
    function recount() { let h = 0; for (let i = 0; i < measure.count; i++) h += measure.itemAt(i) ? measure.itemAt(i).h : 0; rowsHeight = h }
    height: Math.min(parent.height - 80, rowsHeight + Theme.header + 64 + foot.height + 2 * Theme.pad)
    modal: true; closePolicy: QQC.Popup.CloseOnEscape | QQC.Popup.CloseOnPressOutside
    QQC.Overlay.modal: Rectangle { color: Theme.scrim }
    onAboutToShow: settingsPage.reload()
    background: Rectangle { color: Theme.panel; radius: Theme.radiusPanel; border.color: Theme.popupEdge }
    Repeater {   // the height each kit row takes now (what InspectorRow works out), to size the popup to them
        id: measure
        model: settingsPage.rows
        onItemAdded: pop.recount()
        onItemRemoved: pop.recount()
        delegate: Item {
            required property var model
            onHChanged: pop.recount()
            readonly property real h: !model.valid ? 0 : model.row === "group" ? Theme.groupGap + (model.label ? Theme.rowDense : 0)
                                                        : model.row === "more" ? Theme.row + Theme.grid : Theme.row
        }
    }
    contentItem: Item {
        Inspector {
            anchors { left: parent.left; right: parent.right; top: parent.top; bottom: foot.top }
            title: "Preferences"; bridge: settingsPage
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
