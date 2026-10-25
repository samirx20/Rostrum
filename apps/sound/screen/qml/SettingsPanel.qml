import QtQuick
import QtQuick.Controls as QQC
import RostrumKit

// Preferences (screensound/settings_page.py, `settingsPage`): the kit's own Inspector on the settings' field data, so
// it shows only what applies now, most important first; a change is saved at once. Under it: a device fault and the last save's word, if any.
SmallPopup {     // a modal dialog; Esc: the window's one Esc (OpenPopups), a click outside closes it too
    id: pop
    parent: QQC.Overlay.overlay
    // centred when it opens, then its top stays put: a line or row that appears grows it downward, so the row under the
    // pointer never moves away from the next click (it moved up 12 px when "Saved." showed); it moves up only to stay whole
    property real top: 0
    x: Math.round((parent.width - width) / 2)
    y: Math.max(Theme.pad, Math.min(top, parent.height - height - Theme.pad))
    width: 440; padding: 0
    // as tall as its rows need (no empty band under More), up to what the window leaves
    property real rowsHeight: 0
    function recount() { let h = 0; for (let i = 0; i < measure.count; i++) h += measure.itemAt(i) ? measure.itemAt(i).h : 0; rowsHeight = h }
    height: Math.min(parent.height - 80, rowsHeight + 36 + foot.height + 2 * Theme.pad)
    modal: true
    QQC.Overlay.modal: Rectangle { color: Theme.scrim }
    focus: true                                              // the keyboard starts on the sheet, not the window behind
    onAboutToShow: { settingsPage.reload(); top = Math.round((parent.height - height) / 2) }
    onOpened: contentItem.forceActiveFocus()
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
            bridge: settingsPage
        }
        Column {
            id: foot
            anchors { left: parent.left; right: parent.right; bottom: parent.bottom; margins: Theme.pad }
            spacing: Theme.gap
            Text { visible: text !== ""; width: parent.width; wrapMode: Text.WordWrap; text: settingsPage.facts; color: Theme.danger
                   font.family: uiFont; font.pixelSize: Theme.label }
            Item {      // the last save's word beside Done, in room that is always there: "Saved." appearing moves nothing
                width: parent.width; height: Math.max(done.height, said.implicitHeight)
                Text { id: said; objectName: "prefsSaid"
                       anchors { left: parent.left; right: done.left; rightMargin: Theme.gap; verticalCenter: parent.verticalCenter }
                       wrapMode: Text.WordWrap; text: settingsPage.status
                       color: text.indexOf("Error") === 0 ? Theme.danger : Theme.fg2; font.family: uiFont; font.pixelSize: Theme.label }
                Button { id: done; objectName: "prefsDone"; anchors { right: parent.right; verticalCenter: parent.verticalCenter }
                         text: "Done"; kind: "primary"; onClicked: pop.close() }
            }
        }
    }
}
