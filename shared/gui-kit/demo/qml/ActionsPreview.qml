import QtQuick
import QtQuick.Controls as QQC
import RostrumKit

// Look harness for ContextBar, ActionMenu and the Ctrl+K keys, on a fake hub (see actions_preview.py).
QQC.ApplicationWindow {
    id: win
    visible: true; width: 1280; height: 720
    color: Theme.app
    property real barMax: 10000
    function showMenu() { menu.entries = fakeHub.menu(); menu.openAt(520, 300); menu.openSub(2) }
    function showMore() { bar.openMore() }
    function showCommands() { commands.open() }
    function closeAll() { menu.close(); bar.closeMore(); commands.close() }

    Rectangle {
        id: view
        x: 48; y: 0; width: parent.width - 96; height: parent.height
        color: Theme.sunken
        Text { anchors.centerIn: parent; text: "main view"; color: Theme.fg4; font.pixelSize: Theme.heading; font.family: uiFont }
        ContextBar {
            id: bar
            hub: fakeHub; maxWidth: win.barMax
            anchors.top: parent.top; anchors.topMargin: Theme.gap; anchors.horizontalCenter: parent.horizontalCenter
        }
    }
    Rectangle { x: 0; width: 40; height: parent.height; color: Theme.panel }
    ActionMenu { id: menu; onPicked: v => console.log("picked", v) }
    CommandBar { id: commands; bridge: fakeHub }
}
