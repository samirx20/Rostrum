import QtQuick
import QtQuick.Controls as QQC
import RostrumKit

// A plain Sound-like view (tracks with clips and notes) wearing the kit's ContextBar, ActionMenu and CommandBar.
QQC.ApplicationWindow {
    id: win
    visible: true; width: 1280; height: 720
    color: Theme.app
    readonly property int labelW: 120
    function showMenu() { menu.entries = actions.menu(); menu.openAt(560, 330) }
    function showCommands() { commands.open() }
    function closeAll() { menu.close(); commands.close() }

    Rectangle { x: 0; width: 40; height: parent.height; color: Theme.panel }
    Rectangle {
        id: view
        x: 48; width: parent.width - 96; height: parent.height; color: Theme.sunken
        Column {
            y: 64; width: parent.width; spacing: 6
            Repeater {
                model: scene.rows
                delegate: Item {
                    required property var modelData
                    width: view.width; height: 56
                    Rectangle { anchors.fill: parent; color: Theme.panel; radius: 4 }
                    Text { x: Theme.gap; anchors.verticalCenter: parent.verticalCenter; text: modelData.name
                           color: Theme.fg2; font.pixelSize: Theme.body; font.family: uiFont }
                    Repeater {
                        model: modelData.items
                        delegate: Rectangle {
                            required property var modelData
                            readonly property bool picked: scene.selected.indexOf(modelData.id) >= 0
                            x: win.labelW + modelData.x * 0.9; width: Math.max(4, modelData.w * 0.9)
                            y: modelData.type === "clip" ? 6 : 6 + (84 - modelData.pitch) * 1.1
                            height: modelData.type === "clip" ? 44 : 6; radius: 3
                            color: modelData.type === "clip" ? (picked ? Theme.accentSoft : Theme.raised) : (picked ? Theme.accent : Theme.fg3)
                            border.width: modelData.type === "clip" ? 1 : 0; border.color: picked ? Theme.accent : Theme.line
                        }
                    }
                }
            }
        }
        ContextBar {
            hub: actions; maxWidth: view.width - 2 * 48
            anchors.top: parent.top; anchors.topMargin: Theme.gap; anchors.horizontalCenter: parent.horizontalCenter
        }
    }
    ActionMenu { id: menu }
    CommandBar { id: commands; bridge: actions }
}
