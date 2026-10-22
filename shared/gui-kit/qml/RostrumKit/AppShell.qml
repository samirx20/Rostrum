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
    property alias leading: topBar.leading      // the app's left top-bar buttons (File), after the wordmark
    property alias tools: topBar.tools          // the app's own top-bar tools (centred)
    property alias actions: topBar.actions      // the app's action buttons (right, before the command bar)
    property alias helpEntries: topBar.helpEntries   // the app's guides in Help (rostrum_gui.guides.entries), then its own
    signal helpPicked(string value)                  // a Help entry that is neither a guide nor About (the app handles it)
    property int leftWidth: Theme.sidePanel - 32   // 0: no left panel (the centre takes its place, no gap)
    property int rightWidth: Theme.sidePanel       // 0: no right panel
    property int bottomHeight: Theme.timeline
    readonly property alias commandBar: commandBar
    function openCommands(query) { commandBar.open(); if (query) commandBar.query(query) }
    visible: true
    width: 1600; height: 960
    minimumWidth: 1100; minimumHeight: 680
    title: documentName ? documentName + " — " + appName : appName
    color: Theme.app

    function openAbout() { noticesDialog.open() }
    function openHelp() { topBar.openHelp() }
    function openGuide(url) { guideDialog.show(url) }
    function openGuideNamed(file) {       // a scripted step's "guide <file.md>": false when Help has no such guide
        const e = helpEntries.find(x => x.value.endsWith("/" + file))
        if (e) guideDialog.show(e.value)
        return !!e
    }
    Shortcut { sequence: "Ctrl+K"; onActivated: commandBar.open() }
    Shortcut { sequence: "F1"; onActivated: noticesDialog.open() }
    Shortcut { sequence: StandardKey.Undo; enabled: !commandBar.opened; onActivated: win.bridge.undo() }
    Shortcut { sequences: ["Ctrl+Shift+Z", "Ctrl+Y"]; enabled: !commandBar.opened; onActivated: win.bridge.redo() }

    TopBar {
        id: topBar
        anchors { left: parent.left; right: parent.right; top: parent.top }
        bridge: win.bridge; appName: win.appName; documentName: win.documentName
        onCommandClicked: commandBar.open()
        onAboutClicked: noticesDialog.open()
        onGuideClicked: (url) => guideDialog.show(url)
        onHelpPicked: (value) => win.helpPicked(value)
    }
    Item {
        id: body
        anchors { left: parent.left; right: parent.right; top: topBar.bottom; bottom: parent.bottom
                  leftMargin: Theme.gap; rightMargin: Theme.gap; bottomMargin: Theme.gap }
        Item { id: leftSlot; x: 0; width: Math.max(0, win.leftWidth); visible: width > 0; height: bottomSlot.y - Theme.gap }
        Item { id: centreSlot; x: leftSlot.visible ? leftSlot.width + Theme.gap : 0; height: leftSlot.height
               width: (rightSlot.visible ? rightSlot.x - Theme.gap : body.width) - x }
        Item { id: rightSlot; x: body.width - width; width: Math.max(0, win.rightWidth); visible: width > 0; height: leftSlot.height }
        Item { id: bottomSlot; y: body.height - height; width: body.width; height: win.bottomHeight }
    }
    CommandBar { id: commandBar; bridge: win.bridge }
    GuideDialog { id: guideDialog }
    NoticesDialog { id: noticesDialog; data: typeof notices !== "undefined" ? notices : null }
}
