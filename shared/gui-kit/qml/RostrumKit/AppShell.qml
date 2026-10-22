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
    property alias actions: topBar.actions      // the app's action buttons (Export: right, after the command box)
    property alias menu: topBar.menu            // the ≡ button, first in the top bar (optional)
    property alias chips: topBar.chips          // the app's own chips (Sound's loudness), after the agent chip
    property alias saveWord: topBar.saveWord    // "Saved": the top bar reads "Saved · 14 changes"
    // History (Ctrl+H, the change count, the agent chip's Review): a sheet over the right column while open.
    // Apps whose KeyMap makes Ctrl+H too put "history" in its `skip`.
    property bool historyOpen: false
    property string historyFocus: ""            // the run it shows ("" = everything)
    function openHistory(session) { historyFocus = session || ""; historySheet.focusSession = historyFocus; historyOpen = true }
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
    function openConnectAgent(handFor) {  // handFor: an agent id whose "Do it by hand" opens with it (scripted steps)
        agentsDialog.open()
        if (handFor) agentsDialog.toggleHand(handFor)
    }
    function openHelp() { topBar.openHelp() }
    function openGuide(url) { guideDialog.show(url) }
    function openGuideNamed(file) {       // a scripted step's "guide <file.md>": false when Help has no such guide
        const e = helpEntries.find(x => x.value.endsWith("/" + file))
        if (e) guideDialog.show(e.value)
        return !!e
    }
    Shortcut { sequence: "Ctrl+K"; onActivated: commandBar.open() }
    Shortcut { sequence: "F1"; onActivated: noticesDialog.open() }
    Shortcut { sequence: "Ctrl+H"; onActivated: win.historyOpen ? (win.historyOpen = false) : win.openHistory("") }
    Connections { target: win.bridge ? win.bridge.agent : null; function onHistoryAsked(s) { win.openHistory(s) } }
    Shortcut { sequence: StandardKey.Undo; enabled: !commandBar.opened; onActivated: win.bridge.undo() }
    Shortcut { sequences: ["Ctrl+Shift+Z", "Ctrl+Y"]; enabled: !commandBar.opened; onActivated: win.bridge.redo() }

    TopBar {
        id: topBar
        anchors { left: parent.left; right: parent.right; top: parent.top }
        bridge: win.bridge; appName: win.appName; documentName: win.documentName
        onCommandClicked: commandBar.open()
        onAboutClicked: noticesDialog.open()
        onConnectAgentClicked: agentsDialog.open()
        onGuideClicked: (url) => guideDialog.show(url)
        onHelpPicked: (value) => win.helpPicked(value)
    }
    Item {
        id: body
        anchors { left: parent.left; right: parent.right; top: topBar.bottom; bottom: parent.bottom
                  leftMargin: Theme.gap; rightMargin: Theme.gap; bottomMargin: Theme.gap }
        Item { id: leftSlot; x: 0; width: Math.max(0, win.leftWidth); visible: width > 0; height: bottomSlot.y - Theme.gap }
        Item { id: centreSlot; x: leftSlot.visible ? leftSlot.width + Theme.gap : 0; height: leftSlot.height
               width: (win.rightWidth > 0 ? rightSlot.x - Theme.gap : body.width) - x }
        Item { id: rightSlot; x: body.width - width; width: Math.max(0, win.rightWidth); height: leftSlot.height
               visible: width > 0 && !win.historyOpen }   // History takes this column's place: what it hides is not on screen
        Item { id: bottomSlot; y: body.height - height; width: body.width; height: win.bottomHeight }
        HistorySheet {  // in the settings panel's place (the right column; its width at least a side panel's)
            id: historySheet
            visible: win.historyOpen
            z: 5
            width: Math.max(win.rightWidth, Theme.sidePanel); x: body.width - width; height: leftSlot.height
            bridge: win.bridge
            onClosed: win.historyOpen = false
        }
    }
    CommandBar { id: commandBar; bridge: win.bridge }
    GuideDialog { id: guideDialog }
    NoticesDialog { id: noticesDialog; data: typeof notices !== "undefined" ? notices : null }
    ConnectAgentDialog { id: agentsDialog; data: typeof agents !== "undefined" ? agents : null }
}
