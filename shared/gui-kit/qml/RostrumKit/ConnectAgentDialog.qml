import QtQuick
import QtQuick.Controls as QQC
import "."

// Help → Connect an AI agent. Lets a coding agent (Claude, Codex, Cursor …) use this app's tools. Agents found on
// this computer come first, each with "Add to <agent>" (asks first) or "Remove"; every agent has "Do it by hand"
// with the exact command or file text to copy. `data` is the app's `agents` object (rostrum_gui/agents.py).
QQC.Popup {
    id: dlg
    property var data
    property string asking: ""          // the agent whose "Add" waits for the person's yes
    property var openHand: ({})         // agent id -> its by-hand section is open
    readonly property var rows: opened && data ? data.rows : []
    readonly property var found: rows.filter(r => r.installed)
    readonly property var others: rows.filter(r => !r.installed)
    parent: QQC.Overlay.overlay
    x: Math.round((parent.width - width) / 2); y: Math.round((parent.height - height) / 2)
    width: 760; height: Math.min(parent.height - 2 * Theme.groupGap * 2, 720)
    padding: 0
    objectName: "connectAgentDialog"
    modal: true; focus: true
    onOpened: { asking = ""; if (data) data.refresh() }
    QQC.Overlay.modal: Rectangle { color: Theme.scrim }
    background: Rectangle { color: Theme.panel; radius: Theme.radiusPanel; border.color: Theme.popupEdge }
    enter: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.fast } }
    exit: Transition { NumberAnimation { property: "opacity"; from: 1; to: 0; duration: Theme.fast } }

    function toggleHand(id) { const o = Object.assign({}, openHand); o[id] = !o[id]; openHand = o }

    IconButton {
        glyph: "×"; kind: "ghost"; tip: "Close"; z: 2
        anchors { right: parent.right; top: parent.top; margins: Theme.gap }
        onClicked: dlg.close()
    }
    Column {
        id: head
        anchors { left: parent.left; right: parent.right; top: parent.top; margins: Theme.groupGap + Theme.grid }
        spacing: Theme.grid
        Text { text: "Connect an AI agent"; color: Theme.fg; font.family: uiFont; font.pixelSize: 20; font.weight: Font.DemiBold }
        Text {
            width: parent.width - Theme.groupGap * 2; wrapMode: Text.WordWrap
            text: "Let a coding agent use " + (dlg.data ? dlg.data.appName : "this app") + "'s tools: it can build, change, look at and "
                  + "export your work, and every change shows in your history. It works on the project you have open."
            color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body
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
                    Text {
                        text: sec.modelData.title; leftPadding: Theme.grid
                        color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.label; font.weight: Font.DemiBold
                        font.letterSpacing: Theme.capsSpacing; font.capitalization: Font.AllUppercase
                    }
                    Repeater { model: sec.modelData.rows; delegate: agentRow }
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
        width: list.width
        height: body.height + 2 * Theme.pad
        radius: Theme.radiusCtl; color: Theme.sunken
        Column {
            id: body
            x: Theme.pad; y: Theme.pad; width: parent.width - 2 * Theme.pad
            spacing: Theme.gap
            Item {
                width: parent.width; height: Math.max(Theme.button, nameCol.height)
                Column {
                    id: nameCol
                    anchors { left: parent.left; right: buttons.left; rightMargin: Theme.gap; verticalCenter: parent.verticalCenter }
                    spacing: 2
                    Text { text: row.a.name; color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.title; font.weight: Font.DemiBold }
                    Text {
                        width: parent.width; wrapMode: Text.WordWrap
                        text: row.busy ? "Working …"
                            : row.a.state === "ours" ? "Connected. " + (dlg.data ? dlg.data.appName : "") + " is in its list of tools."
                            : row.a.state === "foreign" ? "It already has a server called " + (dlg.data ? dlg.data.server : "") + " that Rostrum didn't add, so Rostrum leaves it alone."
                            : row.a.state.indexOf("error") === 0 ? row.a.state.slice(7)
                            : row.a.installed ? "Not connected yet." : "Not found on this computer."
                        color: row.a.state === "ours" ? Theme.ok : row.a.state.indexOf("error") === 0 ? Theme.danger : Theme.fg3
                        font.family: uiFont; font.pixelSize: Theme.label
                    }
                }
                Row {
                    id: buttons
                    anchors { right: parent.right; verticalCenter: parent.verticalCenter }
                    spacing: Theme.gap
                    Button {
                        visible: row.a.installed && row.a.state === "none" && dlg.asking !== row.a.id && !row.busy
                        text: "Add to " + row.a.name
                        onClicked: dlg.asking = row.a.id
                    }
                    Button {
                        visible: row.a.state === "ours" && !row.busy
                        text: "Remove"; danger: true
                        onClicked: dlg.data.remove(row.a.id)
                    }
                    Button {
                        text: "Do it by hand"; kind: "ghost"; down: !!dlg.openHand[row.a.id]
                        onClicked: dlg.toggleHand(row.a.id)
                    }
                }
            }
            Rectangle {  // asking first: what will change, and where the copy of the old file goes
                visible: dlg.asking === row.a.id
                width: parent.width; height: ask.height + 2 * Theme.gap
                radius: Theme.radiusCtl; color: Theme.accentSoft
                Item {
                    id: ask
                    x: Theme.gap; y: Theme.gap; width: parent.width - 2 * Theme.gap; height: Math.max(askText.height, Theme.button)
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
            Column {  // by hand: the exact text to copy, from the same source as the guides
                visible: !!dlg.openHand[row.a.id]
                width: parent.width; spacing: Theme.gap
                Repeater {
                    model: (row.a.command ? [{ caption: "Command (paste it in a terminal)", text: row.a.command }] : [])
                           .concat([{ caption: (row.a.command ? "Or add this to " : "Add this to ") + row.a.file, text: row.a.snippet }])
                    delegate: Column {
                        id: box
                        required property var modelData
                        width: body.width
                        spacing: Theme.grid
                        Text { text: box.modelData.caption; width: box.width; elide: Text.ElideMiddle; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label }
                        Rectangle {
                            width: box.width; height: code.height + 2 * Theme.gap
                            radius: Theme.radiusCtl; color: Theme.raised
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
                    model: row.a.steps
                    delegate: Text {
                        required property var modelData
                        required property int index
                        width: body.width; wrapMode: Text.WordWrap; textFormat: Text.RichText
                        // `a command` in a step shows in the code font, never with its backticks
                        text: (index + 1) + ".&nbsp; " + modelData.replace(/&/g, "&amp;").replace(/</g, "&lt;")
                              .replace(/`([^`]+)`/g, "<span style=\"font-family:'" + monoFont + "'; color:" + Theme.fg + "\">$1</span>")
                        color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.label
                    }
                }
                Row {
                    spacing: Theme.gap
                    Button { visible: row.a.deeplink !== ""; text: "Open in " + row.a.name; onClicked: dlg.data.openLink(row.a.deeplink) }
                    Button { text: row.a.name + "'s own help page"; kind: "ghost"; onClicked: dlg.data.openLink(row.a.docs) }
                }
            }
        }
    }
    }
}
