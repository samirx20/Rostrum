import QtQuick
import QtQuick.Layouts
import "."

// Wordmark, the app's leading buttons (`leading`: the File button, on the left as in every desktop app), the open
// document's tab, the app's own tools (`tools`: e.g. a page switch, centred), the history status (small), the app's
// action buttons (`actions`: e.g. Export, right side), and the command-bar button.
// Room rules, not fixed widths: the tools stay centred; the left group owns the space up to the tools' left edge (the
// document tab gives way first), the right group the space after the tools' right edge (the status keeps up to 220 px
// while the command button shrinks to its minimum, then the status gives way). Nothing runs into
// anything else, whatever an app puts in its slots.
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

    Row {  // the app's tools sit in the middle of the window
        id: toolsSlot
        anchors.centerIn: parent
        spacing: Theme.gap
        z: 1
    }
    RowLayout {  // left group: up to the tools
        anchors { left: parent.left; right: toolsSlot.left; top: parent.top; bottom: parent.bottom
                  leftMargin: Theme.pad + Theme.gap; rightMargin: Theme.groupGap }
        spacing: Theme.groupGap

        Text { text: bar.appName; color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.title; font.weight: Font.DemiBold }
        Row {  // the app's leading buttons (File)
            id: leadingSlot
            spacing: Theme.gap
            visible: children.length > 0
        }
        Rectangle {
            visible: bar.documentName !== ""
            Layout.fillWidth: true; Layout.minimumWidth: 0
            Layout.maximumWidth: tabLabel.implicitWidth + 2 * Theme.pad
            implicitHeight: Theme.button; implicitWidth: tabLabel.implicitWidth + 2 * Theme.pad
            radius: Theme.radiusCtl; color: Theme.panel
            Text { id: tabLabel; anchors.fill: parent; anchors.leftMargin: Theme.pad; anchors.rightMargin: Theme.pad
                   verticalAlignment: Text.AlignVCenter; elide: Text.ElideMiddle
                   text: bar.documentName; color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body }
        }
        Item { Layout.fillWidth: true }
    }
    RowLayout {  // right group: after the tools
        id: rightGroup
        anchors { left: toolsSlot.right; right: parent.right; top: parent.top; bottom: parent.bottom
                  leftMargin: Theme.groupGap; rightMargin: Theme.gap }
        spacing: Theme.groupGap

        Text {  // the last thing that happened (or what failed), then how many changes: a cut drops the count first
            id: history
            // first claim on up to 220 px (the command button shrinks before this does), never more than there is
            Layout.minimumWidth: Math.max(0, Math.min(implicitWidth, 220, rightGroup.width - actionsSlot.width
                                                      - command.Layout.minimumWidth - help.width - 3 * rightGroup.spacing))
            Layout.fillWidth: true; Layout.preferredWidth: implicitWidth
            horizontalAlignment: Text.AlignRight
            elide: Text.ElideRight
            readonly property string count: bar.bridge.historyCount + (bar.bridge.historyCount === 1 ? " change" : " changes")
            text: bar.bridge.status ? bar.bridge.status + "  ·  " + count : count
            color: /^Error/.test(bar.bridge.status) ? Theme.danger : Theme.fg3
            font.family: uiFont; font.pixelSize: Theme.label
            HoverHandler { id: historyHover }
            HoverTip { text: history.truncated ? history.text : ""; hovered: historyHover.hovered }  // the whole line when cut
        }
        Row {  // the app's action buttons: things to do, not pages to be on
            id: actionsSlot
            spacing: Theme.gap
        }
        Rectangle {
            id: command
            Layout.preferredWidth: 280; Layout.minimumWidth: 150; Layout.maximumWidth: 280; Layout.fillWidth: true
            implicitHeight: Theme.button
            radius: Theme.radiusCtl
            color: cmdHover.containsMouse ? Theme.hover : Theme.raised
            Behavior on color { ColorAnimation { duration: Theme.fast } }
            Text {
                anchors { left: parent.left; leftMargin: Theme.pad; right: cmdKey.left; rightMargin: Theme.grid
                          verticalCenter: parent.verticalCenter }
                elide: Text.ElideRight
                text: "Search or run a command"; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.body
            }
            KeyHint { id: cmdKey; text: "Ctrl K"; anchors.right: parent.right; anchors.rightMargin: Theme.grid; anchors.verticalCenter: parent.verticalCenter }
            MouseArea { id: cmdHover; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: bar.commandClicked() }
        }
        IconButton {  // Help: the app's guides, Connect an AI agent, then About and licences (F1 opens that screen)
            id: help
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
