import QtQuick
import QtQuick.Controls as QQC
import "."

// The window layout every Rostrum app uses:
//   top bar
//   left panel | centre (the app's viewer) | right panel (inspector)
//   timeline — the FULL width, under both side panels
// Panels sit on the app background with a gap (background steps, no lines). The shell also owns the
// keys that every app shares: Ctrl+K command bar, Ctrl+Z undo, Ctrl+Shift+Z / Ctrl+Y redo (the person's own).
QQC.ApplicationWindow {
    id: win
    property var bridge
    property string appName: "Rostrum"
    property string documentName: ""
    property alias left: leftSlot.data
    property alias centre: centreSlot.data
    property alias right: rightSlot.data
    property alias bottom: bottomSlot.data
    property int leftWidth: Theme.sidePanel - 32
    property int rightWidth: Theme.sidePanel
    property int bottomHeight: Theme.timeline
    readonly property alias commandBar: commandBar
    function openCommands(query) { commandBar.open(); if (query) commandBar.query(query) }
    visible: true
    width: 1600; height: 960
    minimumWidth: 1100; minimumHeight: 680
    title: documentName ? documentName + " — " + appName : appName
    color: Theme.app

    Shortcut { sequence: "Ctrl+K"; onActivated: commandBar.open() }
    Shortcut { sequence: StandardKey.Undo; enabled: !commandBar.opened; onActivated: win.bridge.undo() }
    Shortcut { sequences: ["Ctrl+Shift+Z", "Ctrl+Y"]; enabled: !commandBar.opened; onActivated: win.bridge.redo() }

    TopBar {
        id: topBar
        anchors { left: parent.left; right: parent.right; top: parent.top }
        bridge: win.bridge; appName: win.appName; documentName: win.documentName
        onCommandClicked: commandBar.open()
    }
    Item {
        id: body
        anchors { left: parent.left; right: parent.right; top: topBar.bottom; bottom: parent.bottom
                  leftMargin: Theme.gap; rightMargin: Theme.gap; bottomMargin: Theme.gap }
        Item { id: leftSlot; x: 0; width: win.leftWidth; height: bottomSlot.y - Theme.gap }
        Item { id: centreSlot; x: leftSlot.width + Theme.gap; width: rightSlot.x - x - Theme.gap; height: leftSlot.height }
        Item { id: rightSlot; x: body.width - width; width: win.rightWidth; height: leftSlot.height }
        Item { id: bottomSlot; y: body.height - height; width: body.width; height: win.bottomHeight }
    }
    CommandBar { id: commandBar; bridge: win.bridge }
}
