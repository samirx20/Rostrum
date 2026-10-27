import QtQuick
import "."

// History (INTERACTION.md 1.9, 1.18): a sheet in the right column, in the settings panel's place while open.
// Versions at the top (Restore; "Save a version" with a name), a filter (Everyone · You · Agents · Scripts; only once an agent or script has changed something), then every
// step newest first, "who · what · when". An agent's run is one folded row with Keep and Undo all (Bring back once
// taken back); unfolded, each step has Undo this where it can be taken back (not after a later change to the same thing). Taken-back rows are faint and say so. Every button is one new
// change by the person (or, Keep, none); refusals show in the top bar's message in words.
// In an app with goToStep (Sound), a click on a step's words goes back to right after it (taken-back rows: forward to it).
// Reads bridge.historyRows(show), bridge.versions, bridge.agent; `focusSession`: show only that run (Review).
Panel {
    id: sheet
    property var bridge
    // an app that can go back to a step (Sound: goToStep): a click on a step row's words goes back to right after it
    readonly property bool canGo: !!bridge && typeof bridge.goToStep === "function"
    property string focusSession: ""
    property string show: "everyone"
    property var open: ({})                    // which runs are unfolded (screen state): {"<doc>:<seq>": true}
    property var rows: []
    signal closed()
    title: "History"
    bodyRight: Theme.fieldEdge                 // its buttons end where the settings column's fields end
    focus: visible
    // Esc closes it from anywhere: the window's one Esc (AppShell's EscCloses for History)
    property bool others: false                // someone else (an agent, a script) changed something: only then is a filter worth showing
    function reload() {
        others = !!bridge && bridge.historyRows("you").length < bridge.historyRows("everyone").length
        if (!others && show !== "everyone") show = "everyone"
        const all = bridge ? bridge.historyRows(show) : []
        rows = focusSession ? all.filter(r => r.session === focusSession) : all
    }
    onShowChanged: reload()
    onFocusSessionChanged: reload()
    onVisibleChanged: if (visible) reload(); else rows = []     // closed: nothing is held or built
    Component.onCompleted: if (visible) reload()
    readonly property ListView page: pageLoader.item ? pageLoader.item.list : null
    function nameVersion(name) {               // Ctrl+S: the name field, with the time as the default name, selected
        if (!page) return
        const field = page.headerItem.nameField
        page.positionViewAtBeginning()
        field.input.text = name
        field.input.forceActiveFocus()
        field.input.selectAll()
    }
    Connections { target: sheet.bridge; function onDocChanged() { if (sheet.visible) sheet.reload() } }
    headerRight: IconButton { glyph: "×"; kind: "ghost"; tip: "Close  Esc"; onClicked: sheet.closed() }

    component Small: Text {                    // a line of words in the sheet
        color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.label
        elide: Text.ElideRight
    }
    component Act: Button { kind: "normal"; height: Theme.rowDense; implicitHeight: Theme.rowDense }

    Loader {   // the list is built only while the sheet is open
        id: pageLoader
        anchors.fill: parent
        active: sheet.visible
        sourceComponent: Item {   // the list and its bar side by side
            readonly property alias list: list
            ListView {   // rows are made only for what is on screen (a long song has thousands of changes)
                id: list
                anchors.fill: parent
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                spacing: Theme.gap
                model: sheet.rows
                header: Column {
                    readonly property alias nameField: vname
                    bottomPadding: Theme.gap
                    width: list.width
                    spacing: Theme.gap
                    Item { width: 1; height: Theme.grid }
                    Small { text: "Versions"; font.weight: Font.DemiBold; color: Theme.fg3 }
                    Repeater {
                        model: sheet.bridge ? sheet.bridge.versions : []
                        delegate: Item {
                            required property var modelData
                            width: list.width; height: Theme.rowDense
                            Small { anchors.left: parent.left; anchors.right: restore.left; anchors.rightMargin: Theme.gap
                                    anchors.verticalCenter: parent.verticalCenter; color: Theme.fg
                                    text: modelData.name + (modelData.when ? "  ·  " + modelData.when : "") }
                            Act { id: restore; anchors.right: parent.right; text: "Restore"
                                  onClicked: sheet.bridge.restoreVersion(modelData.name) }
                        }
                    }
                    Row {
                        spacing: Theme.gap
                        TextField { id: vname; width: list.width - saveBtn.width - Theme.gap; placeholder: "Name this version"
                                    onEntered: saveBtn.clicked() }
                        Button { id: saveBtn; text: "Save a version"; help: "Name this moment to come back to it later"
                                 onClicked: if (sheet.bridge.saveVersion(vname.input.text)) { vname.input.text = ""; vname.input.focus = false } }
                    }

                    Item { width: 1; height: Theme.grid }
                    Segmented {
                        visible: sheet.focusSession === "" && sheet.others
                        options: [{ value: "everyone", label: "Everyone" }, { value: "you", label: "You" },
                                  { value: "agents", label: "Agents" }, { value: "scripts", label: "Scripts" }]
                        current: sheet.show
                        onPicked: (v) => sheet.show = v
                    }
                    Item {  // Review: one run only, with the way back to everything
                        visible: sheet.focusSession !== ""
                        width: list.width; height: Theme.rowDense
                        Small { anchors.verticalCenter: parent.verticalCenter; text: "One agent run"; color: Theme.fg }
                        Act { anchors.right: parent.right; text: "Show all"; onClicked: sheet.focusSession = "" }
                    }
                    EmptyHint { visible: sheet.rows.length === 0; width: parent.width
                                text: "Changes you and agents make will be listed here." }
                }
                delegate: Column {
                    id: row
                    required property var modelData
                    readonly property string key: modelData.doc + ":" + modelData.seq
                    readonly property bool isRun: modelData.kind === "run"
                    readonly property bool unfolded: isRun && (sheet.focusSession !== "" || !!sheet.open[key])
                    width: list.width
                    spacing: 2
                    Item {
                        width: parent.width; height: Theme.row + (row.isRun ? Theme.rowDense : 0)
                        Chevron { id: fold; visible: row.isRun; x: 0; y: (Theme.row - height) / 2
                                  open: row.unfolded }
                        TapHandler { enabled: row.isRun
                                     onTapped: { const o = Object.assign({}, sheet.open); o[row.key] = !o[row.key]; sheet.open = o } }
                        Small {
                            id: what
                            x: row.isRun ? fold.width + Theme.grid : 0
                            width: parent.width - x - (stepUndo.visible ? stepUndo.width + Theme.gap : 0)
                            height: Theme.row; verticalAlignment: Text.AlignVCenter
                            textFormat: Text.PlainText; color: Theme.fg
                            opacity: row.modelData.undone ? 0.5 : 1      // taken back: faint, its buttons stay clear
                            text: row.modelData.who + " · " + row.modelData.label + (row.modelData.when ? " · " + row.modelData.when : "")
                                  + (row.modelData.undone ? " · taken back" : "")
                            HoverHandler { id: whatHover; cursorShape: sheet.canGo && !row.isRun ? Qt.PointingHandCursor : Qt.ArrowCursor }
                            HoverTip { text: what.truncated ? what.text : ""; hovered: whatHover.hovered }
                            TapHandler { enabled: sheet.canGo && !row.isRun      // go back (or forward) to right after this step
                                         onTapped: sheet.bridge.goToStep(row.modelData.seq, row.modelData.doc) }
                        }
                        Act { id: stepUndo; visible: !row.isRun && row.modelData.undoable; anchors.right: parent.right; y: 2   // only where it can: a later change to the same thing keeps it
                              text: "Undo this"; onClicked: sheet.bridge.undoStep(row.modelData.seq, row.modelData.doc) }
                        Row {  // a run's buttons, under its line
                            visible: row.isRun
                            x: what.x; y: Theme.row - 2
                            spacing: Theme.grid
                            Act { visible: !row.modelData.undone; text: "Keep"
                                  onClicked: { sheet.bridge.agent.keep(); const o = Object.assign({}, sheet.open); o[row.key] = false; sheet.open = o } }
                            Act { visible: !row.modelData.undone; text: "Undo all"; onClicked: sheet.bridge.undoRun(row.modelData.session) }
                            Act { visible: row.modelData.undone; text: "Bring back"; onClicked: sheet.bridge.redoRun(row.modelData.session) }
                        }
                    }
                    Repeater {  // an unfolded run's steps, newest first
                        model: row.unfolded ? row.modelData.steps : []
                        delegate: Item {
                            required property var modelData
                            width: row.width; height: Theme.rowDense
                            opacity: modelData.undone ? 0.5 : 1
                            Small { id: stepWhat; x: Theme.groupGap + Theme.gap; anchors.verticalCenter: parent.verticalCenter
                                    width: parent.width - x - (undoOne.visible ? undoOne.width + Theme.gap : 0)
                                    textFormat: Text.PlainText
                                    text: modelData.label + (modelData.when ? " · " + modelData.when : "") + (modelData.undone ? " · taken back" : "")
                                    HoverHandler { id: stepHover; cursorShape: sheet.canGo ? Qt.PointingHandCursor : Qt.ArrowCursor }
                                    HoverTip { text: stepWhat.truncated ? stepWhat.text : ""; hovered: stepHover.hovered }
                                    TapHandler { enabled: sheet.canGo; onTapped: sheet.bridge.goToStep(modelData.seq, modelData.doc) } }
                            Act { id: undoOne; visible: modelData.undoable; anchors.right: parent.right; text: "Undo this"
                                  onClicked: sheet.bridge.undoStep(modelData.seq, modelData.doc) }
                        }
                    }
                }
            }
            VScrollBar { flick: list }
        }
    }
}
