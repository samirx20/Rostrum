import QtQuick
import QtQuick.Controls as QQC
import "."

// Help → Connect an AI agent. Lets a coding agent (Claude, Codex, Cursor …) use this app's tools. One row per agent
// (agents found on this computer first): its name, then "Add" (asks first), or once connected "● Connected" and
// Remove. One "Set up by hand…" at the foot: pick an agent, get the exact command or file text to copy.
// `data` is the app's `agents` object (rostrum_gui/agents.py).
QQC.Popup {
    id: dlg
    property var data
    property string asking: ""          // the agent whose "Add" waits for the person's yes
    property bool byHand: false         // the by-hand section is open
    property string handId: ""          // the agent it shows ("" = the first one)
    readonly property var rows: opened && data ? data.rows : []
    readonly property var found: rows.filter(r => r.installed)
    readonly property var others: rows.filter(r => !r.installed)
    readonly property var hand: rows.find(r => r.id === handId) || rows[0] || null
    parent: QQC.Overlay.overlay
    x: Math.round((parent.width - width) / 2); y: Math.round((parent.height - height) / 2)
    width: 520    // as tall as its rows (scrolls past the window's room)
    height: Math.min(parent.height - 2 * Theme.groupGap * 2, head.height + list.height + 3 * Theme.groupGap + Theme.grid)
    padding: 0
    objectName: "connectAgentDialog"
    modal: true; focus: true
    onOpened: { asking = ""; byHand = false; if (data) data.refresh() }
    QQC.Overlay.modal: Rectangle { color: Theme.scrim }
    background: Rectangle { color: Theme.panel; radius: Theme.radiusPanel; border.color: Theme.popupEdge }
    enter: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.fast } }
    exit: Transition { NumberAnimation { property: "opacity"; from: 1; to: 0; duration: Theme.fast } }

    function showHand(id) { handId = id; byHand = true }    // Set up by hand, on this agent (AppShell's scripted steps)

    component Caption: Text {
        leftPadding: Theme.grid
        color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.label; font.weight: Font.DemiBold
        font.letterSpacing: Theme.capsSpacing; font.capitalization: Font.AllUppercase
    }

    IconButton {
        glyph: "×"; kind: "ghost"; tip: "Close"; z: 2
        anchors { right: parent.right; top: parent.top; margins: Theme.gap }
        onClicked: dlg.close()
    }
    Column {
        id: head
        anchors { left: parent.left; right: parent.right; top: parent.top; margins: Theme.groupGap + Theme.grid }
        spacing: Theme.grid
        Text {
            text: "Connect an AI agent"; color: Theme.fg; font.family: uiFont; font.pixelSize: 20; font.weight: Font.DemiBold
            HoverHandler { id: titleHover }
            HoverTip { text: "Connect an AI agent"; hovered: titleHover.hovered
                       help: "A coding agent gets " + (dlg.data ? dlg.data.appName : "this app") + "'s tools on the project you "
                             + "have open; every change it makes shows in your history." }
        }
        Text {  // the result of the last Add / Remove, in plain words
            visible: dlg.data && dlg.data.message !== ""
            width: parent.width; wrapMode: Text.WordWrap
            text: dlg.data ? dlg.data.message : ""
            color: dlg.data && dlg.data.messageOk ? Theme.ok : Theme.danger
            font.family: uiFont; font.pixelSize: Theme.label
        }
    }
    Flickable {
        id: flick
        anchors { left: parent.left; right: parent.right; top: head.bottom; bottom: parent.bottom
                  leftMargin: Theme.groupGap; rightMargin: Theme.groupGap; topMargin: Theme.groupGap; bottomMargin: Theme.groupGap }
        contentHeight: list.height; clip: true; boundsBehavior: Flickable.StopAtBounds
        Column {
            id: list
            width: flick.width
            spacing: Theme.groupGap
            Repeater {
                model: [{ title: "On this computer", rows: dlg.found },
                        { title: dlg.found.length ? "Other agents" : "Agents", rows: dlg.others }]
                delegate: Column {
                    id: sec
                    required property var modelData
                    visible: modelData.rows.length > 0
                    width: list.width
                    spacing: Theme.grid
                    Caption { text: sec.modelData.title }
                    Repeater { model: sec.modelData.rows; delegate: agentRow }
                }
            }
            Button {   // the one way in to setting an agent up by hand
                text: dlg.byHand ? "Hide setting up by hand" : "Set up by hand…"; kind: "ghost"
                onClicked: dlg.byHand = !dlg.byHand
            }
            Column {  // by hand: the exact text to copy, from the same source as the guides
                visible: dlg.byHand && !!dlg.hand
                width: list.width; spacing: Theme.gap
                ChoiceField { width: 240; options: dlg.rows.map(r => ({ value: r.id, label: r.name }))
                              current: dlg.hand ? dlg.hand.id : ""; onPicked: (v) => dlg.handId = v }
                Repeater {
                    model: !dlg.hand ? [] : (dlg.hand.command ? [{ caption: "Command (paste it in a terminal)", text: dlg.hand.command }] : [])
                           .concat([{ caption: (dlg.hand.command ? "Or add this to " : "Add this to ") + dlg.hand.file, text: dlg.hand.snippet }])
                    delegate: Column {
                        id: box
                        required property var modelData
                        width: list.width
                        spacing: Theme.grid
                        Text { text: box.modelData.caption; width: box.width; elide: Text.ElideMiddle; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label }
                        Rectangle {
                            width: box.width; height: code.height + 2 * Theme.gap
                            radius: Theme.radiusCtl; color: Theme.sunken
                            Text {
                                id: code
                                anchors { left: parent.left; right: copy.left; top: parent.top; margins: Theme.gap }
                                text: box.modelData.text; wrapMode: Text.WrapAnywhere
                                color: Theme.fg; font.family: monoFont; font.pixelSize: Theme.label
                            }
                            Button { id: copy; text: "Copy"; kind: "ghost"
                                     anchors { right: parent.right; top: parent.top; margins: Theme.grid }
                                     onClicked: dlg.data.copy(box.modelData.text) }
                        }
                    }
                }
                Repeater {
                    model: dlg.hand ? dlg.hand.steps : []
                    delegate: Text {
                        required property var modelData
                        required property int index
                        width: list.width; wrapMode: Text.WordWrap; textFormat: Text.RichText
                        // `a command` in a step shows in the code font, never with its backticks
                        text: (index + 1) + ".&nbsp; " + modelData.replace(/&/g, "&amp;").replace(/</g, "&lt;")
                              .replace(/`([^`]+)`/g, "<span style=\"font-family:'" + monoFont + "'; color:" + Theme.fg + "\">$1</span>")
                        color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.label
                    }
                }
                Row {
                    spacing: Theme.gap
                    Button { visible: !!dlg.hand && dlg.hand.deeplink !== ""; text: dlg.hand ? "Open in " + dlg.hand.name : ""
                             onClicked: dlg.data.openLink(dlg.hand.deeplink) }
                    Button { text: dlg.hand ? dlg.hand.name + "'s own help page" : ""; kind: "ghost"; onClicked: dlg.data.openLink(dlg.hand.docs) }
                }
            }
        }
    }
    VScrollBar { flick: flick }

    Component {
        id: agentRow
        Rectangle {
        id: row
        required property var modelData
        readonly property var a: modelData
        readonly property bool busy: dlg.data && dlg.data.busy === a.id
        readonly property bool error: a.state.indexOf("error") === 0
        // only what is true now, in a few words; the long reason on hover
        readonly property string status: busy ? "Working …" : a.state === "ours" ? "Connected"
                                       : a.state === "foreign" ? "Has its own server" : error ? "Couldn't connect" : ""
        readonly property string why: a.state === "foreign" ? "It already has a server called " + (dlg.data ? dlg.data.server : "")
                                                               + " that Rostrum didn't add, so Rostrum leaves it alone."
                                    : error ? a.state.slice(7) : !a.installed ? "Not found on this computer: set it up by hand." : ""
        width: list.width
        height: body.height
        radius: Theme.radiusCtl; color: a.installed ? Theme.sunken : "transparent"   // only agents we can act on are cards
        Column {
            id: body
            x: Theme.pad; width: parent.width - 2 * Theme.pad
            Item {
                width: parent.width; height: row.a.installed ? 44 : Theme.button + Theme.grid
                Text { id: nameText; anchors { left: parent.left; verticalCenter: parent.verticalCenter }
                       text: row.a.name; color: row.a.installed ? Theme.fg : Theme.fg2
                       font.family: uiFont; font.pixelSize: Theme.body; font.weight: Font.DemiBold }
                Row {
                    anchors { right: parent.right; verticalCenter: parent.verticalCenter }
                    spacing: Theme.gap
                    Row {   // ● Connected (and the other states that are true now)
                        visible: row.status !== ""
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: Theme.grid + 2
                        Rectangle { visible: row.a.state === "ours"; width: 8; height: 8; radius: 4; color: Theme.ok
                                    anchors.verticalCenter: parent.verticalCenter }
                        Text { text: row.status; anchors.verticalCenter: parent.verticalCenter
                               color: row.a.state === "ours" ? Theme.ok : row.error ? Theme.danger : Theme.fg3
                               font.family: uiFont; font.pixelSize: Theme.label }
                    }
                    Button {
                        visible: row.a.installed && row.a.state === "none" && dlg.asking !== row.a.id && !row.busy
                        text: "Add"
                        onClicked: dlg.asking = row.a.id
                    }
                    Button {   // not found here: the way in is its exact text to copy
                        visible: !row.a.installed
                        text: "Set up by hand"; kind: "ghost"
                        onClicked: dlg.showHand(row.a.id)
                    }
                    Button {
                        visible: row.a.state === "ours" && !row.busy
                        text: "Remove"; kind: "ghost"; danger: true
                        onClicked: dlg.data.remove(row.a.id)
                    }
                }
                HoverHandler { id: rowHover }
                HoverTip { text: row.why !== "" ? row.a.name : ""; help: row.why; hovered: rowHover.hovered }
            }
            Item {  // asking first: what will change, and where the copy of the old file goes
                visible: dlg.asking === row.a.id
                width: parent.width; height: visible ? ask.height + Theme.pad : 0
                Item {
                    id: ask
                    width: parent.width; height: Math.max(askText.height, Theme.button)
                    Text {
                        id: askText
                        anchors { left: parent.left; right: askButtons.left; rightMargin: Theme.gap; verticalCenter: parent.verticalCenter }
                        wrapMode: Text.WordWrap
                        text: "Add " + (dlg.data ? dlg.data.server : "") + " to " + row.a.name + "? This changes " + row.a.file
                              + ". Rostrum keeps a copy of the file as it is now, and only ever removes what it added."
                        color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.label
                    }
                    Row {
                        id: askButtons
                        anchors { right: parent.right; verticalCenter: parent.verticalCenter }
                        spacing: Theme.gap
                        Button { text: "Add"; kind: "primary"; onClicked: { dlg.asking = ""; dlg.data.add(row.a.id) } }
                        Button { text: "Cancel"; kind: "ghost"; onClicked: dlg.asking = "" }
                    }
                }
            }
        }
    }
    }
}
