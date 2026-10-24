import QtQuick
import "."

// The top bar, one row in a fixed order (INTERACTION.md 1.1, 1.14):
//   ≡ (`menu`, optional) · app name · leading buttons (`leading`: File) · document tab · message ·
//   "Saved · N changes" (the count only when N > 0) · app tools (`tools`, kept for Sound for now) · chips (the agent chip first, Problems
//   (`problems`), the job (`job`), then `chips`: an app's own, e.g. Sound's loudness) · ↶ ↷ (only when they can act) · command box · `actions` (Export) · ?
// Never shrunk or hidden: "Saved" (the door to History), the tools, ↶ ↷, the actions and ?, and the document tab's
// first 160 px. Nothing is ever cut with "…": when room runs out things give way by priority, never sliding under each
// other. The room is handed out in this order: 1. the chips at full width (else dot and count: `chipsNarrow`, which an
// app chip may read too), 2. the message whole (or none of it) in its fixed slot, which never moves anything, 3. the command box (280 px, then 150, then its search
// icon), 4. the document tab beyond 160 px. A message that is not whole with the full count first drops the count to
// "Saved" (the count moves into Saved's hover); still too long, it steps aside: Saved's hover says it, History keeps it.
// While the agent chip shows, the message is not shown: the agent's words are in the chip's dropdown.
// The change count opens History (historyClicked, and bridge.agent.askHistory, which a kit AppShell listens to).
Item {
    id: bar
    property var bridge
    property string appName: "Rostrum"
    property string documentName: ""
    property bool renamable: false           // click the name to rename the project in place (renameAsked)
    property string saveWord: ""             // the app's save state in a word ("Saved"): "Saved · 14 changes"
    property string historyFocus: ""         // the run History should show (the agent chip's Review), "" = all
    property alias menu: menuSlot.data
    property alias leading: leadingSlot.data
    property alias crumb: crumbSlot.data     // right after the document tab: where in the document you are (3D's "› Hero 01 ▾")
    property alias tools: toolsSlot.data
    property alias chips: chipsSlot.data
    property alias actions: actionsSlot.data
    property var problems: null              // the Problems chip's source ({rows}, jump(row)): ProblemsChip.qml
    property var job: null                   // the running job (the Export sheet's model): JobChip.qml, and Play · Show
                                             // in folder after the message while it says "Exported …"
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
    function reportProblem() {           // ? › Report a problem: the log folder, the details copied, said in the message bar
        const line = notices.reportProblem()
        if (bar.bridge && bar.bridge.say) bar.bridge.say(line); else console.log(line)
    }      // the project's new name, typed on its tab (Enter or leaving the field)
    signal historyClicked()
    implicitHeight: Theme.topBar
    function openHelp() { helpMenu.openFrom(help, "right") }
    function openHistory(session) {
        historyFocus = session || ""
        historyClicked()
        if (bridge && bridge.agent) bridge.agent.askHistory(historyFocus)
    }

    component BarLink: Text {                // a word to click after the message (Play, Show in folder)
        signal clicked()
        anchors.verticalCenter: parent ? parent.verticalCenter : undefined
        height: Math.max(implicitHeight, 16); verticalAlignment: Text.AlignVCenter
        color: linkHover.hovered ? Theme.fg : Theme.accent
        font.family: uiFont; font.pixelSize: Theme.label; font.weight: Font.DemiBold
        HoverHandler { id: linkHover; cursorShape: Qt.PointingHandCursor }
        TapHandler { onTapped: parent.clicked() }
    }
    component Dot: Text { anchors.verticalCenter: parent ? parent.verticalCenter : undefined; text: "·"; color: Theme.fg3
                          font.family: uiFont; font.pixelSize: Theme.label }

    // ---- the room each part gets (widths only; the rows below just place them) ----------------------------------
    readonly property int sp: Theme.groupGap
    readonly property int edgeLeft: Theme.pad + Theme.gap
    readonly property int edgeRight: Theme.gap
    function slot(item) { return item.children.length ? sp + item.implicitWidth : 0 }
    readonly property string undoText: bridge && bridge.undoLabel ? bridge.undoLabel : ""
    readonly property string redoText: bridge && bridge.redoLabel ? bridge.redoLabel : ""
    readonly property real undoWidth: (undoText ? Theme.button : 0) + (redoText ? Theme.button : 0) + (undoText && redoText ? Theme.grid : 0)
    readonly property bool appChips: chipsSlot.children.length > 0
    readonly property bool agentShown: agentChip.info.state !== ""
    readonly property int chipCount: (agentShown ? 1 : 0) + (problemsChip.n > 0 ? 1 : 0) + (jobChip.shown ? 1 : 0) + (appChips ? 1 : 0)
    readonly property real chipsNarrowWidth: (agentShown ? agentChip.narrowWidth : 0) + problemsChip.narrowWidth + jobChip.narrowWidth
                                           + (appChips ? chipsSlot.implicitWidth : 0) + Math.max(0, chipCount - 1) * Theme.gap
    readonly property real chipsExtra: (agentShown ? agentChip.fullWidth - agentChip.narrowWidth : 0)
                                     + problemsChip.fullWidth - problemsChip.narrowWidth + jobChip.fullWidth - jobChip.narrowWidth
    readonly property bool doneLinks: !!job && job.state === "done" && !job.open && job.doneMessage !== "" && bridge.status === job.doneMessage
    readonly property real fixedWidth: edgeLeft + slot(menuSlot) + wordmark.implicitWidth + slot(leadingSlot)
                                     + (tabFloor ? sp + tabFloor : 0) + (crumbSlot.children.length ? crumbSlot.implicitWidth : 0)
                                     + sp + countFull.advanceWidth + slot(toolsSlot)
                                     + (chipsNarrowWidth ? sp + chipsNarrowWidth : 0) + (undoWidth ? sp + undoWidth : 0)
                                     + sp + Theme.button + slot(actionsSlot) + sp + help.width + edgeRight
    readonly property real room: width - fixedWidth                            // what may still be handed out
    // handed out by priority: the chips first, then the whole message, then the command box, then the tab
    readonly property bool chipsNarrow: room < chipsExtra
    readonly property real afterChips: room - (chipsNarrow ? 0 : chipsExtra)
    // the message with what follows it (Play · Show in folder after an export), whole or not at all. It has a FIXED slot
    // (`messageSlot`, there whether or not a message shows), so a message coming or going never moves the command
    // box, the chips or Export: the slot is what is left after the command box's own minimum (150), at most 320 px.
    readonly property real messageNeed: bridge && bridge.status && !agentShown
                                        ? message.implicitWidth + (doneLinks ? Theme.gap + links.implicitWidth : 0) : 0
    readonly property real messageSlot: Math.max(0, Math.min(320, afterChips - (150 - Theme.button) - sp))
    readonly property real countSaving: countShort.text !== "" ? countFull.advanceWidth - countShort.advanceWidth : 0
    readonly property bool messageShown: messageNeed > 0 && messageSlot > 0 && messageNeed <= messageSlot + countSaving
    readonly property bool countShortened: messageShown && messageNeed > messageSlot     // "Saved" alone, for the message
    readonly property real afterMessage: afterChips - (messageSlot > 0 ? sp + messageSlot : 0)
    readonly property real commandWidth: afterMessage >= 150 - Theme.button ? Math.min(280, Theme.button + afterMessage) : Theme.button
    readonly property real afterCommand: afterMessage - (commandWidth - Theme.button)
    readonly property real tabFloor: documentName !== "" ? Math.min(tab.implicitWidth, 160) : 0      // the name's own room
    readonly property real tabWidth: tabFloor ? tabFloor + Math.max(0, Math.min(tab.implicitWidth - tabFloor, afterCommand)) : 0
    readonly property int changes: agentShown || !bridge ? 0 : bridge.historyCount   // (the agent chip counts its own)
    readonly property string changesWord: changes > 0 ? changes + (changes === 1 ? " change" : " changes") : ""
    TextMetrics { id: countFull; font: count.font; text: [bar.saveWord, bar.changesWord].filter(w => w).join(" · ") }
    TextMetrics { id: countShort; font: count.font; text: bar.saveWord && bar.changesWord ? bar.saveWord : "" }

    Row {  // left group: ≡ (the app's menu button), wordmark, leading buttons, the document tab, the crumb
        id: leftGroup
        x: bar.edgeLeft; anchors.verticalCenter: parent.verticalCenter
        spacing: bar.sp
        Row { id: menuSlot; anchors.verticalCenter: parent.verticalCenter; visible: children.length > 0 }
        Text { id: wordmark; anchors.verticalCenter: parent.verticalCenter; text: bar.appName; color: Theme.fg
               font.family: uiFont; font.pixelSize: Theme.title; font.weight: Font.DemiBold }
        Row {  // the app's leading buttons (File)
            id: leadingSlot
            anchors.verticalCenter: parent.verticalCenter
            spacing: Theme.gap
            visible: children.length > 0
        }
        Rectangle {
            id: tab
            visible: bar.documentName !== "" && bar.tabWidth > 0
            anchors.verticalCenter: parent.verticalCenter
            implicitWidth: bar.documentName !== "" ? tabLabel.implicitWidth + 2 * Theme.pad : 0
            width: bar.tabWidth; height: Theme.button
            radius: Theme.radiusCtl
            objectName: "projectName"
            property bool editing: false
            function rename() { editing = true; nameField.input.forceActiveFocus(); nameField.input.selectAll() }
            color: editing ? Theme.panel : tabArea.containsMouse ? Theme.hover : "transparent"   // plain text at rest, as in Figma; a box only when hovered or renamed
            Text { id: tabLabel; anchors.fill: parent; anchors.leftMargin: Theme.pad; anchors.rightMargin: Theme.pad
                   visible: !tab.editing; verticalAlignment: Text.AlignVCenter; elide: Text.ElideMiddle
                   text: bar.documentName; color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body
                   HoverHandler { id: tabHover }
                   HoverTip { text: tabLabel.truncated ? bar.documentName : bar.renamable ? "Rename" : ""
                              help: bar.renamable ? "Click to rename the project." : ""; hovered: tabHover.hovered } }
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
    Row {  // the crumb, tight after the tab (no group gap: it reads as one "project › shot")
        id: crumbSlot
        x: leftGroup.x + leftGroup.width + (tab.visible ? 0 : bar.sp); anchors.verticalCenter: parent.verticalCenter
        visible: children.length > 0
    }
    Row {  // right group: message, the change count, tools, chips, ↶ ↷, the command box, actions, Help
        id: rightGroup
        anchors.right: parent.right; anchors.rightMargin: bar.edgeRight; anchors.verticalCenter: parent.verticalCenter
        spacing: bar.sp
        Item {   // the message's fixed slot (see messageSlot): the message sits at its right edge, next to "Saved"
            id: messageSlotItem
            anchors.verticalCenter: parent.verticalCenter
            visible: bar.messageSlot > 0
            width: bar.messageSlot + (bar.countShortened ? bar.countSaving : 0); height: Theme.button
            Row {
                anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                spacing: Theme.gap
                visible: bar.messageShown     // (not message.visible: a child's reads its parent's)
                Text {  // the last thing that happened (or what failed): whole or not at all, never "…"
                    id: message
                    visible: bar.messageShown
                    anchors.verticalCenter: parent.verticalCenter
                    text: bar.bridge.status || ""
                    color: bar.bridge.statusFailed ? Theme.danger : Theme.fg3
                    font.family: uiFont; font.pixelSize: Theme.label
                }
                Row {   // after an export: "Exported Main.mp4 · Play · Show in folder ·" (until the next message)
                    id: links
                    visible: bar.doneLinks && message.visible
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: Theme.gap
                    BarLink { text: "Play"; onClicked: bar.job.play() }
                    Dot { }
                    BarLink { text: "Show in folder"; onClicked: bar.job.showInFolder() }
                }
            }
        }
        Text {  // "Saved · 14 changes" ("Saved" with none, or while a message needs the room): its own piece, the door
            id: count   // to History. While the agent chip shows, the count is the chip's ("Claude · 6 changes"): "Saved" alone
            anchors.verticalCenter: parent.verticalCenter
            height: Math.max(implicitHeight, 16); verticalAlignment: Text.AlignVCenter     // a click target of at least 16 px
            text: bar.countShortened ? countShort.text : countFull.text
            visible: text !== ""
            color: countHover.hovered ? Theme.fg : Theme.fg2; font.family: uiFont; font.pixelSize: Theme.label
            HoverHandler { id: countHover; cursorShape: Qt.PointingHandCursor }
            TapHandler { onTapped: bar.openHistory("") }
            // what gave way for the room is said here: the count, or a message that stepped aside
            HoverTip { text: "Open History"; key: "Ctrl H"; hovered: countHover.hovered
                       help: [bar.countShortened ? bar.changesWord : "",
                              bar.messageNeed > 0 && !bar.messageShown ? bar.bridge.status : ""].filter(w => w).join(" · ") }
        }
        Row {  // the app's tools (kept for apps that still use them; never shrinks)
            id: toolsSlot
            anchors.verticalCenter: parent.verticalCenter
            spacing: Theme.gap
            visible: children.length > 0
        }
        Row {  // chips: each only while it has something to say
            anchors.verticalCenter: parent.verticalCenter
            spacing: Theme.gap
            visible: bar.chipCount > 0
            AgentChip { id: agentChip; bridge: bar.bridge; narrow: bar.chipsNarrow; anchors.verticalCenter: parent.verticalCenter
                        width: implicitWidth; height: implicitHeight
                        onReview: (session) => { bar.historyFocus = session; bar.historyClicked() } }
            ProblemsChip { id: problemsChip; source: bar.problems; narrow: bar.chipsNarrow; anchors.verticalCenter: parent.verticalCenter
                           width: implicitWidth; height: implicitHeight }
            JobChip { id: jobChip; job: bar.job; narrow: bar.chipsNarrow; anchors.verticalCenter: parent.verticalCenter
                      width: implicitWidth; height: implicitHeight }
            Row { id: chipsSlot; anchors.verticalCenter: parent.verticalCenter; spacing: Theme.gap; visible: children.length > 0 }
        }
        Row {  // ↶ ↷: each only while it can act; the tip names the step
            anchors.verticalCenter: parent.verticalCenter
            spacing: Theme.grid
            visible: bar.undoWidth > 0
            IconButton { visible: bar.undoText !== ""; glyph: "↶"; kind: "ghost"; tip: "Undo: " + bar.undoText + "  Ctrl Z"
                         onClicked: bar.bridge.undo() }
            IconButton { visible: bar.redoText !== ""; glyph: "↷"; kind: "ghost"; tip: "Redo: " + bar.redoText + "  Ctrl Shift Z"
                         onClicked: bar.bridge.redo() }
        }
        Rectangle {  // the command box; with little room just its search icon (still the same button)
            id: command
            readonly property bool iconOnly: width < 150
            anchors.verticalCenter: parent.verticalCenter
            width: bar.commandWidth; height: Theme.button
            radius: Theme.radiusCtl
            color: cmdHover.containsMouse ? Theme.hover : Theme.raised
            Behavior on color { ColorAnimation { duration: Theme.fast } }
            Item {  // a drawn magnifier (a font glyph differs per font)
                id: lens
                width: 14; height: 14
                x: command.iconOnly ? (command.width - width) / 2 : Theme.pad - 2
                anchors.verticalCenter: parent.verticalCenter
                Rectangle { width: 10; height: 10; radius: 5; color: "transparent"; border.width: 1.5; border.color: Theme.fg3 }
                Rectangle { x: 8; y: 10; width: 6; height: 1.5; radius: 1; rotation: 45; color: Theme.fg3 }
            }
            Text {      // the words fit or say less, never cut mid-word: "Search or run a command", else "Search"
                id: cmdWords
                visible: !command.iconOnly
                anchors { left: lens.right; leftMargin: Theme.gap; right: cmdKey.left; rightMargin: Theme.grid
                          verticalCenter: parent.verticalCenter }
                readonly property string full: "Search or run a command"
                TextMetrics { id: fullWidth; font: cmdWords.font; text: cmdWords.full }
                text: fullWidth.advanceWidth <= width ? full : "Search"; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.body
            }
            KeyHint { id: cmdKey; visible: !command.iconOnly; text: "Ctrl K"
                      anchors.right: parent.right; anchors.rightMargin: Theme.grid; anchors.verticalCenter: parent.verticalCenter }
            MouseArea { id: cmdHover; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: bar.commandClicked() }
            HoverTip { text: command.iconOnly || cmdWords.text !== cmdWords.full ? "Search or run a command  Ctrl K" : ""; hovered: cmdHover.containsMouse
                       pressed: cmdHover.pressed }
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
            icon: "help"; kind: "ghost"; tip: "Help"; help: "Guides, keys, connecting an AI agent, reporting a problem, About."; down: helpMenu.opened
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
                                : v === "report" ? bar.reportProblem()
                                : v === "guides" ? bar.guidesClicked() : v === "keys" ? bar.keysClicked()
                                : /^file:.*\.md$/i.test(v) ? bar.guideClicked(v) : bar.helpPicked(v)
            }
        }
    }
}
