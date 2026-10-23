import QtQuick
import QtQuick.Controls as QQC
import "."
import "FrameLayout.js" as FrameLayout

// The window layout every Rostrum app uses:
//   top bar
//   left panel | centre (the app's viewer) | right panel (inspector)
//   timeline — the FULL width, under both side panels
// Panels sit on the app background with a gap (background steps, no lines). The shell also owns the
// keys that every app shares: Ctrl+K command bar, Ctrl+Z undo, Ctrl+Shift+Z / Ctrl+Y redo (the person's own),
// Ctrl+H History, F1 the guides drawer, Ctrl+/ the key list, F6 the next area, Ctrl+\ fold the side panels
// (the kit's KeyMap leaves these to the shell: its `shell` list).
// Focus (INTERACTION.md 1.20): the area last clicked (rostrum_gui/focus_areas.py calls pressedAt) has a thin accent
// line on its top edge; whenever the keys would land nowhere (a dialog closed, Esc or Enter in a field) they go back to
// the work (backToWork: the main view).
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
    function openHistory(session) { historyFocus = session || ""; historySheet.focusSession = historyFocus; panelsFolded = false; historyOpen = true }
    function nameVersion(name) { openHistory(""); historySheet.nameVersion(name) }   // Ctrl+S (FilesMenu): History's name field
    // Export (EXPORT.md): the app's rostrum_gui.export_sheet.ExportSheet. Its sheet takes the same column; one sheet at a
    // time (opening one closes the other). Ctrl+E opens / closes it, Ctrl+Shift+E exports again without opening it;
    // the job chip and "Play · Show in folder" after the message come with it. `exportSettings`: the chosen item's
    // own settings rows, inside the sheet.
    property var exporter: null
    property alias exportSettings: exportSheet.settings
    readonly property bool exportOpen: !!exporter && exporter.open
    property alias problems: topBar.problems    // the Problems chip's source ({rows}, jump(row))
    onHistoryOpenChanged: if (historyOpen && exportOpen) exporter.setOpen(false)
    onExportOpenChanged: if (exportOpen) { historyOpen = false; panelsFolded = false }
    property alias helpEntries: topBar.helpEntries   // the app's guides (rostrum_gui.guides.entries; the drawer lists them), then its own
    signal helpPicked(string value)                  // a Help entry that is neither a guide nor About (the app handles it)
    property int leftWidth: Theme.sidePanel - 32   // 0: no left panel (the centre takes its place, no gap)
    property int rightWidth: Theme.sidePanel       // 0: no right panel
    property int bottomHeight: Theme.timeline
    // The frame drives the layout (FrameLayout.js, SPEC 2d-design-v2 §1.2): an app with a frame sets `frameAspect`
    // (> 0), what its centre column spends besides the frame's well (`frameChrome`) and the timeline's least height;
    // the shell then sizes the settings panel and the timeline (below the frame, or beside it for tall and square
    // frames) and rightWidth / bottomHeight are not used. `frameFolded` >= 0: the timeline folded to that height.
    // A panel edge dragged by hand wins and is remembered per arrangement (panelSizes, the person's settings);
    // a double-click on the edge gives it back. `layoutChanged()`: the time to fit the frame again (never otherwise).
    property real frameAspect: 0
    property size frameChrome: Qt.size(0, 0)
    property int timelineLeast: Theme.timeline
    property int frameFolded: -1
    signal layoutChanged()
    property int askedRev: 0                       // bumps when a hand size changes (panelSizes is not a binding)
    function asked(kind, panel) { askedRev; return typeof panelSizes !== "undefined" ? panelSizes.get(kind, panel) : -1 }
    function setAsked(panel, size) {
        if (typeof panelSizes === "undefined" || !frameLayout) return
        panelSizes.set(frameLayout.kind, panel, size < 0 ? -1 : Math.round(size)); askedRev++
    }
    readonly property var frameLayout: frameAspect > 0 && body.width > 0 && body.height > 0 ? FrameLayout.solve({
        W: body.width, H: body.height, aspect: frameAspect, gap: Theme.gap, chromeW: frameChrome.width, chromeH: frameChrome.height,
        tlLeast: timelineLeast,
        asked: { stacked: { right: asked("stacked", "right"), bottom: asked("stacked", "bottom") },
                 side: { right: asked("side", "right"), bottom: asked("side", "bottom") } } }) : null
    readonly property bool bottomBeside: !!frameLayout && frameLayout.kind === "side"
    readonly property int rightNow: frameLayout ? frameLayout.right : rightWidth
    // folding the timeline moves nothing else: the canvas area grows, the frame stays where it is (§4.1)
    readonly property int bottomNow: frameLayout ? (bottomBeside ? body.height : frameFolded >= 0 ? frameFolded : frameLayout.bottom) : bottomHeight
    readonly property string frameKey: frameLayout ? [frameLayout.kind, frameLayout.right, frameLayout.bottom, Math.round(frameLayout.frameW), Math.round(frameLayout.frameH)].join(" ") : ""
    onFrameKeyChanged: Qt.callLater(win.layoutChanged)
    readonly property alias commandBar: commandBar
    // the key for a key map job ("Ctrl+E"), for hover help (Button / IconButton `job`); "" without one
    readonly property var allKeys: bridge && bridge.actions ? bridge.actions.keys
                                 : typeof sharedKeys !== "undefined" ? sharedKeys : []   // the app's key map, else the shared one
    readonly property var keyNames: {
        const out = {}
        const keys = win.allKeys
        for (const k of keys) if (k.keys.length && !(k.job in out)) out[k.job] = k.keys[0]
        return out
    }
    function keyFor(job) { return keyNames[job] || "" }
    // the guides drawer (F1, ? › Guides): on the left beside the main view, in the left panel's place while open
    property bool guidesOpen: false
    readonly property int guidesWidth: guidesOpen ? guidesDrawer.width + Theme.gap : 0   // a full-window cover (the start screen) leaves this much room
    function openGuides() { guidesOpen = true; focusArea = "guides"; guidesDrawer.forceActiveFocus() }
    function closeGuides() { guidesOpen = false; backToWork() }
    // focus: which area takes the keys ("guides", "left", "centre", "right", "bottom"); apps may name them for
    // inspect_screen (`areaNames`: {centre: "canvas", bottom: "timeline"}), sent to bridge.setFocusArea
    property string focusArea: "centre"
    property var areaNames: ({})
    property bool panelsFolded: false           // Ctrl+\: the side panels fold away (the main view takes their room)
    onFocusAreaChanged: if (bridge && bridge.setFocusArea) bridge.setFocusArea(areaNames[focusArea] || focusArea)
    function rightItem() { return historySheet.visible ? historySheet : exportSheet.visible ? exportSheet : rightSlot }
    function backToWork() { focusArea = "centre"; centreSlot.forceActiveFocus() }
    function areas() {
        return [["guides", guidesDrawer], ["left", leftSlot], ["centre", centreSlot],
                ["right", win.rightItem()], ["bottom", bottomSlot]]
               .filter(a => a[1].visible && a[1].width > 0 && a[1].height > 0)
    }
    function pressedAt(x, y) {                  // a press anywhere in the window (focus_areas.py): its area
        const p = body.mapFromItem(null, x, y)
        for (const [name, it] of areas())
            if (p.x >= it.x && p.x < it.x + it.width && p.y >= it.y && p.y < it.y + it.height) { focusArea = name; return }
    }
    function nextArea() {                       // F6
        const order = areas()
        const next = order[(order.findIndex(a => a[0] === focusArea) + 1) % order.length]
        focusArea = next[0]; next[1].forceActiveFocus()
    }
    onActiveFocusItemChanged: if (activeFocusItem === null || activeFocusItem === contentItem) Qt.callLater(win.settle)
    function settle() { if (activeFocusItem === null || activeFocusItem === contentItem) backToWork() }
    function openCommands(query) { commandBar.open(); if (query) commandBar.query(query) }
    visible: true
    width: 1600; height: 960
    minimumWidth: 1100; minimumHeight: 680
    title: documentName ? documentName + " — " + appName : appName
    color: Theme.app

    function openAbout() { noticesDialog.open() }
    function openConnectAgent(handFor) {  // handFor: an agent id whose Set up by hand opens with it (scripted steps)
        agentsDialog.open()
        if (handFor) agentsDialog.showHand(handFor)
    }
    function openHelp() { topBar.openHelp() }
    function openGuide(url) { guidesDrawer.show(url); openGuides() }
    function openGuideNamed(file) {       // a scripted step's "guide <file.md>": false when the app has no such guide
        const e = helpEntries.find(x => x.value.endsWith("/" + file))
        if (e) openGuide(e.value)
        return !!e
    }
    function openKeys() { keyList.open() }
    Shortcut { sequence: "Ctrl+K"; onActivated: commandBar.open() }
    Shortcut { sequence: "F1"; onActivated: win.guidesOpen ? win.closeGuides() : win.openGuides() }
    Shortcut { sequence: "Ctrl+/"; onActivated: keyList.opened ? keyList.close() : keyList.open() }
    Shortcut { sequence: "F6"; onActivated: win.nextArea() }
    Shortcut { sequence: "Ctrl+\\"; onActivated: { win.panelsFolded = !win.panelsFolded; if (win.panelsFolded) win.historyOpen = false } }
    Shortcut { sequence: "Ctrl+H"; onActivated: win.historyOpen ? (win.historyOpen = false) : win.openHistory("") }
    Connections { target: win.bridge ? win.bridge.agent : null; function onHistoryAsked(s) { win.openHistory(s) } }
    Shortcut { sequence: "Ctrl+E"; enabled: !!win.exporter; onActivated: win.exporter.setOpen(!win.exporter.open) }
    Shortcut { sequence: "Ctrl+Shift+E"; enabled: !!win.exporter; onActivated: win.exporter.again() }
    Shortcut { sequences: [StandardKey.Undo]; enabled: !commandBar.opened; onActivated: win.bridge.undo() }
    Shortcut { sequences: ["Ctrl+Shift+Z", "Ctrl+Y"]; enabled: !commandBar.opened; onActivated: win.bridge.redo() }

    TopBar {
        id: topBar
        anchors { left: parent.left; right: parent.right; top: parent.top }
        bridge: win.bridge; appName: win.appName; documentName: win.documentName
        renamable: typeof files !== "undefined" && !!files && files.hasProject     // the kit's files (project_files.py)
        onRenameAsked: (name) => files.rename(name)
        job: win.exporter
        onCommandClicked: commandBar.open()
        onAboutClicked: noticesDialog.open()
        onConnectAgentClicked: agentsDialog.open()
        onGuideClicked: (url) => win.openGuide(url)
        onGuidesClicked: win.openGuides()
        onKeysClicked: keyList.open()
        onHelpPicked: (value) => win.helpPicked(value)
    }
    Item {
        id: body
        anchors { left: parent.left; right: parent.right; top: topBar.bottom; bottom: parent.bottom
                  leftMargin: Theme.gap; rightMargin: Theme.gap; bottomMargin: Theme.gap }
        readonly property int rightNow: win.panelsFolded ? 0 : Math.max(0, win.rightNow)
        readonly property int besideNow: win.bottomBeside ? win.frameLayout.bottom + Theme.gap : 0   // a timeline beside the frame
        GuidesDrawer {  // the guides: the left drawer, pushing the main view aside (never over it); the left panel's place
            id: guidesDrawer
            visible: win.guidesOpen
            x: 0; width: visible ? Math.min(360, Math.round(body.width * 0.3)) : 0; height: leftSlot.height
            entries: win.helpEntries
            onClosed: win.closeGuides()
        }
        Item { id: leftSlot; x: 0; width: win.guidesOpen || win.panelsFolded ? 0 : Math.max(0, win.leftWidth)
               visible: width > 0; height: win.bottomBeside ? body.height : bottomSlot.y - Theme.gap }
        Item { id: centreSlot
               x: guidesDrawer.visible ? guidesDrawer.width + Theme.gap : leftSlot.visible ? leftSlot.width + Theme.gap : 0
               height: leftSlot.height
               width: (body.rightNow > 0 ? rightSlot.x - Theme.gap : body.width) - body.besideNow - x }
        Item { id: rightSlot; x: body.width - width; width: body.rightNow; height: win.bottomBeside ? body.height : bottomSlot.y - Theme.gap
               visible: width > 0 && !win.historyOpen && !win.exportOpen }   // a sheet takes this column's place: what it hides is not on screen
        Item { id: bottomSlot   // across the bottom, or beside the frame (between the centre and the settings panel)
               x: win.bottomBeside ? centreSlot.x + centreSlot.width + Theme.gap : 0
               y: body.height - height; height: win.bottomNow
               width: win.bottomBeside ? win.frameLayout.bottom : body.width }
        PanelEdge {     // the settings panel's edge: dragged, its width is the person's; double-click: automatic again
            visible: !!win.frameLayout && rightSlot.visible; vertical: true
            x: rightSlot.x - Theme.gap; y: 0; width: Theme.gap; height: rightSlot.height
            onMoved: (d) => win.setAsked("right", win.frameLayout.right - d)
            onReset: win.setAsked("right", -1)
        }
        PanelEdge {     // a timeline beside the frame: its left edge sets its width
            visible: win.bottomBeside; vertical: true
            x: bottomSlot.x - Theme.gap; y: 0; width: Theme.gap; height: bottomSlot.height
            onMoved: (d) => win.setAsked("bottom", win.frameLayout.bottom - d)
            onReset: win.setAsked("bottom", -1)
        }
        HistorySheet {  // in the settings panel's place (the right column; its width at least a side panel's)
            id: historySheet
            visible: win.historyOpen
            z: 5
            width: Math.max(win.rightNow, Theme.sidePanel); x: body.width - width; height: rightSlot.height
            bridge: win.bridge
            onClosed: { win.historyOpen = false; win.backToWork() }
        }
        ExportSheet {   // the same place, one sheet at a time
            id: exportSheet
            visible: win.exportOpen
            z: 5
            width: Math.max(win.rightNow, Theme.sidePanel); x: body.width - width; height: rightSlot.height
            model: win.exporter
        }
        Rectangle {     // the focused area's accent edge, only when keys go somewhere other than the main view (home)
            readonly property Item at: ({ guides: guidesDrawer, left: leftSlot, centre: centreSlot, bottom: bottomSlot,
                                          right: win.rightItem() })[win.focusArea] || centreSlot
            visible: at !== centreSlot && at.visible && at.width > 0
            x: at.x + Theme.radiusPanel; width: Math.max(0, at.width - 2 * Theme.radiusPanel); y: at.y; height: 2
            radius: 1; color: Theme.accent; opacity: 0.8; z: 6
        }
    }
    CommandBar { id: commandBar; bridge: win.bridge; onClosed: win.backToWork() }
    KeyList { id: keyList; keys: win.allKeys; onDone: win.backToWork() }
    NoticesDialog { id: noticesDialog; data: typeof notices !== "undefined" ? notices : null; onClosed: win.backToWork() }
    ConnectAgentDialog { id: agentsDialog; data: typeof agents !== "undefined" ? agents : null; onClosed: win.backToWork() }
}
