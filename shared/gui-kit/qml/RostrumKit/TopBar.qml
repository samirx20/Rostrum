import QtQuick
import "."

// Wordmark, the app's leading buttons (`leading`: the File button, on the left as in every desktop app), the open
// document's tab, the app's own tools (`tools`: e.g. a page switch, centred), what just happened and the change
// count, the app's action buttons (`actions`: e.g. Export), the command box and Help.
// Room rules, so nothing ever runs under anything else, whatever an app puts in its slots: the wordmark, the leading
// buttons, the change count, the actions and Help never shrink. When room runs out, things give way in one fixed
// order: first the "what just happened" message (cut with "…", down to nothing; hover shows all of it), then the
// document tab, then the command box (280 px, then 150, then just its search icon). The tools stay centred while
// that collides with nothing; otherwise they slide toward the left group, never under it.
Item {
    id: bar
    property var bridge
    property string appName: "Rostrum"
    property string documentName: ""
    property alias leading: leadingSlot.data
    property alias tools: toolsSlot.data
    property alias actions: actionsSlot.data
    // The app's own Help entries, above About: {value, label}. A guide's value is its .md file's file:// address
    // (rostrum_gui.guides.entries; it opens in the kit's guide viewer); any other value is the app's own entry
    // and comes back as helpPicked(value). Apps with an agent server (an `agents` object, rostrum_gui/agents.py)
    // also get "Connect an AI agent", just above About.
    property var helpEntries: []
    signal commandClicked()
    signal aboutClicked()
    signal connectAgentClicked()
    signal guideClicked(string url)
    signal helpPicked(string value)
    implicitHeight: Theme.topBar
    function openHelp() { helpMenu.open() }

    // ---- the room each part gets (widths only; the rows below just place them) ----------------------------------
    readonly property int sp: Theme.groupGap
    readonly property int edgeLeft: Theme.pad + Theme.gap
    readonly property int edgeRight: Theme.gap
    readonly property real toolsWidth: toolsSlot.children.length ? toolsSlot.implicitWidth : 0
    readonly property real fixedWidth: edgeLeft + wordmark.implicitWidth + (leadingSlot.children.length ? sp + leadingSlot.implicitWidth : 0)
                                     + (toolsWidth ? 2 * sp + toolsWidth : sp)
                                     + count.implicitWidth + (actionsSlot.children.length ? sp + actionsSlot.implicitWidth : 0)
                                     + sp + Theme.button + sp + help.width + edgeRight      // the command box as its icon
    readonly property real room: width - fixedWidth                            // what may still be handed out
    // handed out in the reverse of the give-way order: the command box first, then the tab, then the message
    readonly property real commandWidth: room >= 150 - Theme.button ? Math.min(280, Theme.button + room) : Theme.button
    readonly property real afterCommand: room - (commandWidth - Theme.button)
    readonly property real tabWidth: fit(tab.implicitWidth, afterCommand - sp, 48)
    readonly property real afterTab: afterCommand - (tabWidth ? tabWidth + sp : 0)
    // the message never pushes the tools off centre (they'd jump about with every message): with tools, only the
    // room right of the centred tools
    readonly property real rightOfTools: toolsWidth ? width - edgeRight - (width + toolsWidth) / 2 - sp
                                                      - count.implicitWidth - (actionsSlot.children.length ? sp + actionsSlot.implicitWidth : 0)
                                                      - sp - commandWidth - sp - help.width
                                                    : afterTab
    readonly property real messageWidth: fit(message.implicitWidth, Math.min(afterTab, rightOfTools) - Theme.gap, 24)
    // a part gets its natural width or what is there; below `least` it gives way entirely (a short name that fits whole
    // always shows: "t1 •" is narrower than `least`)
    function fit(natural, there, least) { const w = Math.min(natural, Math.max(0, there)); return w >= Math.min(least, natural) && w > 0 ? w : 0 }

    Row {  // left group: wordmark, leading buttons, the document tab
        id: leftGroup
        x: bar.edgeLeft; anchors.verticalCenter: parent.verticalCenter
        spacing: bar.sp
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
            radius: Theme.radiusCtl; color: Theme.panel
            Text { id: tabLabel; anchors.fill: parent; anchors.leftMargin: Theme.pad; anchors.rightMargin: Theme.pad
                   verticalAlignment: Text.AlignVCenter; elide: Text.ElideMiddle
                   text: bar.documentName; color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body }
        }
    }
    Row {  // the app's tools: centred while that collides with nothing, else as far toward the centre as fits
        id: toolsSlot
        anchors.verticalCenter: parent.verticalCenter
        x: Math.max(leftGroup.x + leftGroup.width + bar.sp,
                    Math.min((bar.width - width) / 2, rightGroup.x - bar.sp - width))
        spacing: Theme.gap
        z: 1
    }
    Row {  // right group: what just happened, the change count, the actions, the command box, Help
        id: rightGroup
        anchors.right: parent.right; anchors.rightMargin: bar.edgeRight; anchors.verticalCenter: parent.verticalCenter
        spacing: bar.sp
        Row {
            anchors.verticalCenter: parent.verticalCenter
            spacing: Theme.gap
            Text {  // the last thing that happened (or what failed): gives way first, hover shows all of it
                id: message
                visible: bar.messageWidth > 0
                width: bar.messageWidth
                anchors.verticalCenter: parent.verticalCenter
                text: bar.bridge.status ? bar.bridge.status + "  ·" : ""
                elide: Text.ElideRight
                color: /^Error/.test(bar.bridge.status) ? Theme.danger : Theme.fg3
                font.family: uiFont; font.pixelSize: Theme.label
                HoverHandler { id: messageHover }
                HoverTip { text: message.truncated ? bar.bridge.status : ""; hovered: messageHover.hovered }
            }
            Text {  // how many changes: never shrinks
                id: count
                anchors.verticalCenter: parent.verticalCenter
                text: bar.bridge.historyCount + (bar.bridge.historyCount === 1 ? " change" : " changes")
                color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label
            }
        }
        Row {  // the app's action buttons: things to do, not pages to be on
            id: actionsSlot
            anchors.verticalCenter: parent.verticalCenter
            spacing: Theme.gap
            visible: children.length > 0
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
            Text {
                visible: !command.iconOnly
                anchors { left: lens.right; leftMargin: Theme.gap; right: cmdKey.left; rightMargin: Theme.grid
                          verticalCenter: parent.verticalCenter }
                elide: Text.ElideRight
                text: "Search or run a command"; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.body
            }
            KeyHint { id: cmdKey; visible: !command.iconOnly; text: "Ctrl K"
                      anchors.right: parent.right; anchors.rightMargin: Theme.grid; anchors.verticalCenter: parent.verticalCenter }
            MouseArea { id: cmdHover; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: bar.commandClicked() }
            HoverTip { text: command.iconOnly ? "Search or run a command  Ctrl K" : ""; hovered: cmdHover.containsMouse
                       pressed: cmdHover.pressed }
        }
        IconButton {  // Help: the app's guides, Connect an AI agent, then About and licences (F1 opens that screen)
            id: help
            anchors.verticalCenter: parent.verticalCenter
            glyph: "?"; kind: "ghost"; tip: "Help"; down: helpMenu.opened
            onClicked: helpMenu.open()
            Menu {
                id: helpMenu
                x: parent.width - width
                width: 240
                entries: bar.helpEntries
                    .concat(typeof agents !== "undefined" && agents ? [{ value: "agents", label: "Connect an AI agent" }] : [])
                    .concat([{ value: "about", label: "About and licences" }])
                onPicked: (v) => v === "about" ? bar.aboutClicked() : v === "agents" ? bar.connectAgentClicked()
                                : /^file:.*\.md$/i.test(v) ? bar.guideClicked(v) : bar.helpPicked(v)
            }
        }
    }
}
