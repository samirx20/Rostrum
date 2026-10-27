import QtQuick
import "."

// The top bar, ONE 40 px row that is also the window's title bar (header-design SPEC §3-§5; INTERACTION.md 1.1, 1.14):
//   app mark ▾ (`appIcon`; opens the `menu` slot's FilesMenu) · leading buttons (`leading`) · the project name (click to
//   rename; a dot on it while saving is not happening: `saveState`) · the crumb (`crumb`, tight after it: "› Main ▾") ·
//   the message · … `tools` (3D's pages: centred in the window, else midway between the groups) … · chips (the agent
//   chip, Problems (`problems`), the job (`job`), then `chips`: an app's own, e.g. Sound's loudness) · Undo, Redo,
//   History · the command box ("Search  Ctrl K", 200 px; only its icon below a 1400 px window) · `actions` (Export) · ?
//   · then, when the window is drawn by us (`windowChrome.merged`), 8 px and the three window buttons flush right.
// Everything in the bar that is not a button, chip, field or the name is the window's drag area (the message text too):
// press and move moves the window, a double-click maximises, a right-click opens Windows' window menu. The bar tells
// Windows where its clickable things are (`windowChrome.setZones`, once after any layout change, never per frame).
// Saving is automatic, so there is no "Saved": only when it is NOT happening, an amber dot on the name ("unsaved", e.g.
// a sample) or a red one ("failed"), its words on hover, and "● " in front of the window title (AppShell).
// The message (what just happened) sits after the crumb, small and grey, and fades after 4 s; a failure stays, red,
// until the next message. A finished export is the job chip's ("Exported Main.mp4 ▾": Play, Show in folder).
// Never shrunk or hidden: the mark, Undo / Redo / History, the actions, ?, the window buttons, the pages (`tools`) and the
// name's first 160 px. Nothing is ever cut with "…": when room runs out things give way by priority, never sliding under
// each other. The room is handed out in this order: 1. the chips at full width (else dot and count: `chipsNarrow`, which
// an app chip may read too), 2. the message whole (or none of it) in its fixed slot (at most 320 px), which never moves
// anything, 3. the command box (200 px from a 1400 px window, else its search icon), 4. the name beyond 160 px.
// A message longer than its slot (a refusal, a failure) must still be read where it happened: it takes the command box's
// room (the box folds to its icon) and the name's, until the next message; still too long, it is said on two lines.
// Never dropped: only a window too narrow even for two lines leaves it to the name's hover.
// While the agent chip shows, the message is not shown: the agent's words are in the chip's dropdown.
// Undo and Redo hold their places while they can't act (an empty place, not a greyed button), so the first edit or undo
// never moves the bar; History (the clock, Ctrl+H) opens History (historyClicked, and bridge.agent.askHistory).
// Another window in front (`windowChrome.active` false): the name and crumb dim, the mark loses its colour, the window
// buttons dim; Export keeps its colour. Height and places never change.
// An action a person started that runs past 0.2 s: a thin moving line on the bar's lower edge, its words below it at the
// right, from 1 s its job chip with Cancel (WorkingLine.qml, rostrum_gui/ack.py); over the bar, so nothing in it moves.
Item {
    id: bar
    objectName: "topBar"
    property var bridge
    property string appName: "Rostrum"
    property string appIcon: ""              // the app's mark: a picture's address or a kit mark's name (AppMark.qml)
    property string documentName: ""
    property bool renamable: false           // click the name to rename the project in place (renameAsked)
    property string saveState: ""            // "" (saved after every change, or nothing to save), "unsaved", "failed"
    property string saveWords: ""            // the dot's hover: "Not saved: this is the sample", "Can't save: the disk is full"
    property string historyFocus: ""         // the run History should show (the agent chip's Review), "" = all
    property alias menu: menuSlot.data
    property alias leading: leadingSlot.data
    property alias crumb: crumbSlot.data     // right after the name: where in the document you are (3D's "› Hero 01 ▾")
    property alias tools: toolsSlot.data
    property alias chips: chipsSlot.data
    property alias actions: actionsSlot.data
    property var problems: null              // the Problems chip's source ({rows}, jump(row)): ProblemsChip.qml
    property var job: null                   // the running job (the Export sheet's model): JobChip.qml
    // The app's own Help entries, above About: {value, label}. A guide's value is its .md file's file:// address
    // (rostrum_gui.guides.entries; it opens in the kit's guide viewer); any other value is the app's own entry
    // and comes back as helpPicked(value). Apps with an agent server (an `agents` object, rostrum_gui/agents.py)
    // also get "Connect an AI agent", just above About.
    property var helpEntries: []
    signal commandClicked()
    signal aboutClicked()
    signal connectAgentClicked()
    signal guideClicked(string url)
    signal guidesClicked()               // ? › Guides (F1): the guides drawer
    signal keysClicked()                 // ? › Keys (Ctrl+/): the key list
    signal helpPicked(string value)
    signal renameAsked(string name)
    signal reportClicked()               // ? › Report a problem: its small window (ReportDialog.qml)
    // (renameAsked: the project's new name, typed on its tab, Enter or leaving the field)
    signal historyClicked()
    implicitHeight: Theme.topBar
    function openHelp() { helpMenu.openFrom(help, "right") }
    function openProblems() { if (problemsChip.n > 0) problemsChip.openList() }       // Ctrl+K's "Problems"
    function openHistory(session) {
        historyFocus = session || ""
        historyClicked()
        if (bridge && bridge.agent) bridge.agent.askHistory(historyFocus)
    }

    readonly property bool merged: windowChrome.merged
    readonly property bool active: windowChrome.active

    // ---- the room each part gets (widths only; the rows below just place them) ----------------------------------
    readonly property int sp: Theme.groupGap
    readonly property int edgeLeft: Theme.pad
    readonly property real edgeRight: merged ? Theme.gap + windowButtons.width : Theme.gap
    function slot(item) { return item.children.length ? sp + item.implicitWidth : 0 }
    readonly property string undoText: bridge && bridge.undoLabel ? bridge.undoLabel : ""
    readonly property string redoText: bridge && bridge.redoLabel ? bridge.redoLabel : ""
    readonly property real timeWidth: 3 * Theme.button + 2 * Theme.grid        // Undo, Redo, History: places always held
    readonly property real markWidth: menuSlot.children.length ? mark.width : 0
    readonly property bool appChips: chipsSlot.children.length > 0
    readonly property bool agentShown: agentChip.info.state !== ""
    readonly property int chipCount: (agentShown ? 1 : 0) + (problemsChip.n > 0 ? 1 : 0) + (jobChip.shown ? 1 : 0) + (appChips ? 1 : 0)
    readonly property real chipsNarrowWidth: (agentShown ? agentChip.narrowWidth : 0) + problemsChip.narrowWidth + jobChip.narrowWidth
                                           + (appChips ? chipsSlot.implicitWidth : 0) + Math.max(0, chipCount - 1) * Theme.gap
    readonly property real chipsExtra: (agentShown ? agentChip.fullWidth - agentChip.narrowWidth : 0)
                                     + problemsChip.fullWidth - problemsChip.narrowWidth + jobChip.fullWidth - jobChip.narrowWidth
    // a finished export: its chip says so while the message still does (until the next message)
    readonly property bool jobDone: !!job && job.state === "done" && !job.open && !!job.doneMessage && !!bridge && bridge.status === job.doneMessage
    readonly property real toolsWidth: toolsSlot.children.length ? toolsSlot.implicitWidth : 0
    readonly property real fixedWidth: edgeLeft + markWidth + slot(leadingSlot) + (tabFloor ? (markWidth || leadingSlot.children.length ? sp : 0) + tabFloor : 0)
                                     + (crumbSlot.children.length ? crumbSlot.implicitWidth : 0)
                                     + (toolsWidth ? sp + toolsWidth : 0)          // the pages are fixed room (SPEC §8 step 5)
                                     + (chipsNarrowWidth ? sp + chipsNarrowWidth : 0) + sp + timeWidth
                                     + sp + Theme.button + slot(actionsSlot) + sp + help.width + edgeRight
    readonly property real room: width - fixedWidth                            // what may still be handed out
    // handed out by priority: the chips first, then the whole message, then the command box, then the name
    readonly property bool chipsNarrow: room < chipsExtra
    readonly property real afterChips: room - (chipsNarrow ? 0 : chipsExtra)
    readonly property real boxExtra: width >= 1400 ? 200 - Theme.button : 0   // the command box beyond its icon
    // the message, whole, never cut. Its slot is FIXED (there whether or not a message shows): what is left after the
    // command box, at most 320 px, so a usual message coming or going never moves the box, the chips or Export.
    readonly property real messageSlot: Math.max(0, Math.min(320, afterChips - boxExtra - sp))
    // (not while the agent chip shows: its words are in the chip; nor while the job chip says the export finished)
    readonly property string messageText: bridge && bridge.status && !agentShown && !jobDone ? bridge.status : ""
    TextMetrics { id: messageOneLine; font: message.font; text: bar.messageText }
    readonly property real messageNeed: messageText ? Math.ceil(messageOneLine.advanceWidth) : 0
    // longer than that (a refusal, a failure): it takes the command box's room (the box folds to its icon) and the
    // name's, until the next message
    readonly property bool messageLong: messageNeed > messageSlot
    readonly property real messageRoom: messageLong ? Math.max(0, Math.min(messageNeed, afterChips - sp)) : messageSlot
    readonly property bool boxWide: boxExtra > 0 && afterChips - sp - messageRoom >= boxExtra
    readonly property real commandWidth: Theme.button + (boxWide ? boxExtra : 0)
    readonly property real afterCommand: afterChips - sp - messageRoom - (boxWide ? boxExtra : 0)
    readonly property real tabFloor: documentName !== "" ? Math.min(tab.implicitWidth, 160) : 0      // the name's own room
    readonly property real tabWidth: tabFloor ? tabFloor + Math.max(0, Math.min(tab.implicitWidth - tabFloor, afterCommand)) : 0
    // where the left part ends (the crumb, else the name) and the pages: centred in the window when that leaves a
    // group gap on the left and a control gap before the right group (its first thing may be Undo's held, empty place;
    // and a midway place moves whenever a chip comes or goes), else midway between the groups
    readonly property real leftEnd: crumbSlot.visible ? crumbSlot.x + crumbSlot.width : leftGroup.x + leftGroup.width
    readonly property real toolsX: {
        const centred = Math.round((width - toolsWidth) / 2)
        if (centred >= leftEnd + sp && centred + toolsWidth <= rightGroup.x - Theme.gap) return centred
        return Math.round((leftEnd + rightGroup.x - toolsWidth) / 2)
    }
    // the message's room, never past the pages
    readonly property real messageX: leftEnd + sp
    readonly property real messageFits: Math.max(0, Math.min(messageRoom, (toolsWidth ? toolsX : rightGroup.x) - sp - messageX))
    readonly property bool messageOneFits: messageNeed > 0 && messageNeed <= messageFits
    // still too long for one line in that room: two lines (the bar holds two at the label size), whole words
    readonly property bool messageWraps: messageNeed > 0 && messageFits > 0 && !messageOneFits
                                         && twoLines.lineCount <= 2 && twoLines.implicitHeight <= height - 4
    Text { id: twoLines; visible: false; width: bar.messageFits; wrapMode: Text.WordWrap
           text: bar.messageText; font: message.font; lineHeight: message.lineHeight }
    readonly property bool messageShown: messageOneFits || messageWraps
    // the message fades 4 s after it came; a failure stays until the next message. Pictures and layout checks (drawn
    // offscreen) keep it, so they show what was said.
    readonly property bool fades: Qt.platform.pluginName !== "offscreen"
    property bool messageFresh: true
    Timer { id: fadeTimer; interval: 4000; running: bar.fades; onTriggered: bar.messageFresh = false }
    Connections { target: bar.bridge; ignoreUnknownSignals: true
                  function onStatusChanged() { bar.messageFresh = true; if (bar.fades) fadeTimer.restart() } }
    readonly property bool messageLit: messageFresh || !fades || (!!bridge && bridge.statusFailed)

    Row {  // left group: the app mark-menu, leading buttons, the name
        id: leftGroup
        x: bar.edgeLeft; anchors.verticalCenter: parent.verticalCenter
        spacing: bar.sp
        Item {
            id: markSlot
            visible: menuSlot.children.length > 0
            anchors.verticalCenter: parent.verticalCenter
            width: mark.width; height: mark.height
            Row { id: menuSlot; opacity: 0; anchors.verticalCenter: parent.verticalCenter }   // the app's menu button: invisible, under the mark, it opens the menu
            AppMark { id: mark; appIcon: bar.appIcon; target: menuSlot.children.length ? menuSlot.children[0] : null; active: bar.active }
        }
        Row {  // the app's leading buttons
            id: leadingSlot
            anchors.verticalCenter: parent.verticalCenter
            spacing: Theme.gap
            visible: children.length > 0
        }
        Rectangle {
            id: tab
            visible: bar.documentName !== "" && bar.tabWidth > 0
            anchors.verticalCenter: parent.verticalCenter
            readonly property real dotRoom: bar.saveState !== "" ? Theme.gap + 6 : 0
            implicitWidth: bar.documentName !== "" ? tabLabel.implicitWidth + dotRoom + 2 * Theme.pad : 0
            width: bar.tabWidth; height: Theme.button
            radius: Theme.radiusCtl
            objectName: "projectName"
            property bool editing: false
            function rename() { editing = true; nameField.input.forceActiveFocus(); nameField.input.selectAll() }
            color: editing ? Theme.panel : tabArea.containsMouse ? Theme.hover : "transparent"   // plain text at rest, as in Figma; a box only when hovered or renamed
            Text { id: tabLabel; anchors.fill: parent; anchors.leftMargin: Theme.pad; anchors.rightMargin: Theme.pad + tab.dotRoom
                   visible: !tab.editing; verticalAlignment: Text.AlignVCenter; elide: Text.ElideMiddle
                   text: bar.documentName; color: bar.active ? Theme.fg : Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body
                   HoverHandler { id: tabHover }
                   // the tip: what the dot means, else the whole name when it is cut, and a message that had no room
                   HoverTip { text: bar.saveState === "failed" ? "Can't save" : bar.saveState !== "" ? "Not saved"
                                    : tabLabel.truncated ? bar.documentName : bar.renamable ? "Rename" : ""
                              help: [bar.saveWords, bar.renamable ? "Click to rename the project." : "",
                                     bar.messageNeed > 0 && !bar.messageShown ? bar.bridge.status : ""].filter(w => w).join(" ")
                              hovered: tabHover.hovered } }
            Rectangle {   // not saving: amber ("unsaved"), red ("failed")
                objectName: "saveDot"
                visible: bar.saveState !== "" && !tab.editing
                width: 6; height: 6; radius: 3
                x: tab.width - Theme.pad - width; anchors.verticalCenter: parent.verticalCenter
                color: bar.saveState === "failed" ? Theme.danger : Theme.warn
            }
            MouseArea { id: tabArea; anchors.fill: parent; enabled: bar.renamable && !tab.editing; hoverEnabled: true
                        cursorShape: Qt.IBeamCursor
                        onClicked: tab.rename() }
            TextField {   // the name, typed in place: Enter or leaving the field renames, Esc keeps it
                id: nameField
                anchors.fill: parent; visible: tab.editing; value: bar.documentName
                onEdited: (v) => { tab.editing = false; if (v.trim() && v.trim() !== bar.documentName) bar.renameAsked(v.trim()) }
                onEscaped: tab.editing = false
                Connections { target: nameField.input
                              function onActiveFocusChanged() { if (!nameField.input.activeFocus) tab.editing = false } }
            }
        }
    }
    Row {  // the crumb, tight after the name (no group gap: it reads as one "project › shot")
        id: crumbSlot
        x: leftGroup.x + leftGroup.width + (tab.visible || !leftGroup.width ? 0 : bar.sp); anchors.verticalCenter: parent.verticalCenter
        visible: children.length > 0
        opacity: bar.active ? 1 : 0.7
    }
    Text {  // the last thing that happened (or what failed): whole on one line or two, never "…"; drag area, no handler
        id: message
        x: bar.messageX; anchors.verticalCenter: parent.verticalCenter
        visible: bar.messageShown
        opacity: bar.messageLit ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: Theme.reduceMotion ? 0 : 600 } }
        width: bar.messageWraps ? twoLines.width : implicitWidth
        wrapMode: bar.messageWraps ? Text.WordWrap : Text.NoWrap; lineHeight: 0.95
        text: bar.messageText
        color: bar.bridge.statusFailed ? Theme.danger : Theme.fg3
        font.family: uiFont; font.pixelSize: Theme.label
    }
    Row {  // the app's pages (3D: Build / Animate / Render): centred in the window, else midway between the groups
        id: toolsSlot
        x: bar.toolsX; anchors.verticalCenter: parent.verticalCenter
        spacing: Theme.gap
        visible: children.length > 0
    }
    Row {  // right group: chips, Undo Redo History, the command box, actions, Help
        id: rightGroup
        anchors.right: parent.right; anchors.rightMargin: bar.edgeRight; anchors.verticalCenter: parent.verticalCenter
        spacing: bar.sp
        Row {  // chips: each only while it has something to say
            id: chipsRow
            anchors.verticalCenter: parent.verticalCenter
            spacing: Theme.gap
            visible: bar.chipCount > 0
            AgentChip { id: agentChip; bridge: bar.bridge; narrow: bar.chipsNarrow; anchors.verticalCenter: parent.verticalCenter
                        width: implicitWidth; height: implicitHeight
                        onReview: (session) => { bar.historyFocus = session; bar.historyClicked() } }
            ProblemsChip { id: problemsChip; source: bar.problems; narrow: bar.chipsNarrow; anchors.verticalCenter: parent.verticalCenter
                           width: implicitWidth; height: implicitHeight }
            JobChip { id: jobChip; job: bar.job; narrow: bar.chipsNarrow; doneShown: bar.jobDone; anchors.verticalCenter: parent.verticalCenter
                      width: implicitWidth; height: implicitHeight }
            Row { id: chipsSlot; anchors.verticalCenter: parent.verticalCenter; spacing: Theme.gap; visible: children.length > 0 }
        }
        Row {  // Undo, Redo (each only while it can act; the tip names the step; both places stay, so neither moves under
               // the pointer and nothing beside them moves), then History
            id: timeRow
            anchors.verticalCenter: parent.verticalCenter
            spacing: Theme.grid
            Item {
                width: Theme.button; height: Theme.button
                IconButton { id: undoButton; visible: bar.undoText !== ""; objectName: "undoButton"; icon: "undo"; iconSize: 16; kind: "ghost"
                             tip: "Undo: " + bar.undoText + "  Ctrl Z"; onClicked: bar.bridge.undo() }
            }
            Item {
                width: Theme.button; height: Theme.button
                IconButton { id: redoButton; visible: bar.redoText !== ""; objectName: "redoButton"; icon: "redo"; iconSize: 16; kind: "ghost"
                             tip: "Redo: " + bar.redoText + "  Ctrl Shift Z"; onClicked: bar.bridge.redo() }
            }
            IconButton { id: historyButton; objectName: "historyButton"; icon: "history"; iconSize: 16; kind: "ghost"
                         tip: "History"; help: "Every change, back to the start; go back to any of them or name a version."
                         job: "history"; onClicked: bar.openHistory("") }
        }
        Rectangle {  // the command box; below a 1400 px window (or with little room) just its search icon (the same button)
            id: command
            objectName: "commandBox"
            readonly property bool iconOnly: !bar.boxWide
            anchors.verticalCenter: parent.verticalCenter
            width: bar.commandWidth; height: Theme.button
            radius: Theme.radiusCtl
            color: cmdHover.containsMouse ? Theme.hover : Theme.raised
            Behavior on color { ColorAnimation { duration: Theme.fast } }
            ToolIcon { id: lens; name: "search"; width: 16; height: 16; ink: Theme.fg3
                       x: command.iconOnly ? (command.width - width) / 2 : Theme.gap; anchors.verticalCenter: parent.verticalCenter }
            Text { visible: !command.iconOnly; text: "Search"; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.body
                   anchors { left: lens.right; leftMargin: Theme.gap; verticalCenter: parent.verticalCenter } }
            KeyHint { id: cmdKey; visible: !command.iconOnly; text: "Ctrl K"
                      anchors.right: parent.right; anchors.rightMargin: Theme.grid; anchors.verticalCenter: parent.verticalCenter }
            MouseArea { id: cmdHover; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: bar.commandClicked() }
            HoverTip { text: "Search or run a command  Ctrl K"; hovered: cmdHover.containsMouse; pressed: cmdHover.pressed }
        }
        Row {  // the app's action buttons (Export): things to do, not pages to be on
            id: actionsSlot
            anchors.verticalCenter: parent.verticalCenter
            spacing: Theme.gap
            visible: children.length > 0
        }
        IconButton {  // ? (INTERACTION.md 1.17): Guides (F1, the drawer lists the app's guides), Keys, Connect an AI agent,
                      // the app's own entries, then About and licences
            id: help
            objectName: "helpButton"
            anchors.verticalCenter: parent.verticalCenter
            icon: "help"; iconSize: 16; kind: "ghost"; tip: "Help"; help: "Guides, keys, connecting an AI agent, reporting a problem, About."; down: helpMenu.opened
            onClicked: helpMenu.openFrom(help, "right")
            Menu {
                id: helpMenu
                width: 240
                entries: [{ value: "guides", label: "Guides", keys: "F1" }, { value: "keys", label: "Keys", keys: "Ctrl /" }]
                    .concat(typeof agents !== "undefined" && agents ? [{ value: "agents", label: "Connect an AI agent…" }] : [])
                    .concat(bar.helpEntries.filter(e => !/^file:.*\.md$/i.test(e.value)))
                    .concat(typeof notices !== "undefined" && notices ? [{ value: "report", label: "Report a problem…" }] : [])
                    .concat([{ value: "about", label: "About and licences" }])
                onPicked: (v) => v === "about" ? bar.aboutClicked() : v === "agents" ? bar.connectAgentClicked()
                                : v === "report" ? bar.reportClicked()
                                : v === "guides" ? bar.guidesClicked() : v === "keys" ? bar.keysClicked()
                                : /^file:.*\.md$/i.test(v) ? bar.guideClicked(v) : bar.helpPicked(v)
            }
        }
    }
    WindowButtons {   // minimise, maximise / restore, close: flush right, the bar's full height (window_chrome.py)
        id: windowButtons
        visible: bar.merged
        anchors.right: parent.right; anchors.top: parent.top
        height: Theme.topBar
    }

    // ---- where Windows lets the pointer click (everything else in the bar moves the window) ---------------------
    // Every clickable thing in the bar, in window pixels, handed to windowChrome once after any layout change; the
    // maximise button apart (Windows treats it as its own, for the snap layouts).
    function slotItems(row) { const out = []; for (let i = 0; i < row.children.length; i++) out.push(row.children[i]); return out }
    function zoneItems() {   // under the start screen (OpenPopups.covered) only its window buttons, in the same place: the
                             // rest of the strip is drag room there
        if (OpenPopups.covered) return [windowButtons.minButton, windowButtons.closeButton]
        return [mark].concat(slotItems(leadingSlot), [tab], slotItems(crumbSlot), slotItems(toolsSlot),
                             [agentChip, problemsChip, jobChip], slotItems(chipsSlot), [undoButton, redoButton, historyButton, command],
                             slotItems(actionsSlot), [help, windowButtons.minButton, windowButtons.closeButton])
    }
    function rectOf(it) { const p = it.mapToItem(null, 0, 0); return [Math.round(p.x), Math.round(p.y), Math.round(it.width), Math.round(it.height)] }
    function shown(it) { let p = it; while (p && p !== bar) { if (!p.visible || p.opacity < 0.05) return false; p = p.parent } return it.width > 0 && it.height > 0 }
    function pushZones() {
        if (!merged) return
        windowChrome.setZones(zoneItems().filter(it => it && shown(it)).map(rectOf),
                              windowButtons.visible ? rectOf(windowButtons.maxButton) : [])
    }
    // what moves a zone: the bar's size, each group's place and each clickable thing's place, size and visibility
    readonly property string zoneKey: !merged ? "" : [width, leftGroup.x, leftGroup.width, crumbSlot.x, toolsSlot.x, rightGroup.x, chipsRow.width,
                                                      actionsSlot.width, windowButtons.x, OpenPopups.covered]
        .concat(zoneItems().map(it => it ? [it.x, it.y, it.width, it.height, it.visible, it.parent ? it.parent.x : 0].join(",") : "")).join(" ")
    onZoneKeyChanged: Qt.callLater(pushZones)

    WorkingLine { anchors.left: parent.left; anchors.right: parent.right; y: parent.height - height; height: implicitHeight; z: 5 }
}
