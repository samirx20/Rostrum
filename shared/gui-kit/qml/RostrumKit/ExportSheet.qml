import QtQuick
import QtQuick.Controls as QQC
import QtQuick.Dialogs
import "."

// Export (INTERACTION.md 1.19 item 8): a sheet in the right column, in the settings panel's place, so the work stays in
// sight. One heading (its title), then what for (a short list in words, each with its file type) · the chosen one's settings (`settings`: the app
// fills it with kit rows) · range (only when the document has more than everything) · where (the project's Renders
// folder; Browse) · the file's name · Export. A file already there is never replaced without asking: Replace / Keep
// both / Cancel, the one blocking question. The export runs in the background (the top bar's job chip); done, the
// message line says "Exported Main.mp4 · Play · Show in folder". A failure is red, in words; the old file stays.
// `model`: the app's rostrum_gui.export_sheet.ExportSheet. Esc or × closes it.
Panel {
    id: sheet
    property var model
    property alias settings: settingsSlot.data      // the chosen item's settings only (the app's rows)
    readonly property bool running: model && model.state === "running"
    title: "Export"
    focus: visible
    Keys.onEscapePressed: model.setOpen(false)
    headerRight: IconButton { glyph: "×"; kind: "ghost"; tip: "Close  Esc"; onClicked: sheet.model.setOpen(false) }

    component Caption: Text {
        color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label
        font.weight: Font.DemiBold; font.letterSpacing: Theme.capsSpacing; font.capitalization: Font.AllUppercase
    }
    component Line: Text {                // one line that shortens in the middle; hover shows all of it
        id: line
        width: parent.width; elide: Text.ElideMiddle
        color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body
        HoverHandler { id: lineHover }
        HoverTip { text: line.truncated ? line.text : ""; hovered: lineHover.hovered }
    }
    component Link: Text {                // a word to click in the result line
        signal clicked()
        color: linkHover.hovered ? Theme.fg : Theme.accent
        height: Math.max(implicitHeight, 16); verticalAlignment: Text.AlignVCenter
        font.family: uiFont; font.pixelSize: Theme.body; font.weight: Font.DemiBold
        HoverHandler { id: linkHover; cursorShape: Qt.PointingHandCursor }
        TapHandler { onTapped: parent.clicked() }
    }

    Flickable {
        id: flick
        anchors { left: parent.left; right: parent.right; top: parent.top; bottom: footer.top }
        contentHeight: col.height + Theme.pad
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        Column {
            id: col
            width: flick.width
            spacing: Theme.gap

            Column {        // the app's choices, in words, each with its file type (the sheet's title is the one heading)
                width: parent.width
                Repeater {
                    model: sheet.model ? sheet.model.choices : []
                    delegate: Rectangle {
                        id: choiceRow
                        required property var modelData
                        readonly property bool chosen: sheet.model.choice === modelData.value
                        width: col.width; height: Theme.rowDense
                        radius: Theme.radiusCtl
                        color: chosen ? Theme.accentSoft : choiceHover.hovered ? Theme.hover : "transparent"
                        Text { id: kindText; anchors.right: parent.right; anchors.rightMargin: Theme.gap; anchors.verticalCenter: parent.verticalCenter
                               text: choiceRow.modelData.type || ""; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label }
                        Text { anchors { left: parent.left; leftMargin: Theme.gap; right: kindText.left; rightMargin: Theme.gap
                                         verticalCenter: parent.verticalCenter }
                               text: choiceRow.modelData.label; elide: Text.ElideRight
                               color: choiceRow.chosen ? Theme.fg : Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body }
                        HoverHandler { id: choiceHover; cursorShape: Qt.PointingHandCursor }
                        TapHandler { onTapped: sheet.model.setChoice(choiceRow.modelData.value) }
                    }
                }
            }
            Column { id: settingsSlot; width: parent.width; spacing: Theme.gap; visible: children.length > 0 }

            Item { width: 1; height: Theme.grid }
            Column {        // only when the document has more than "everything" (markers, a time range)
                visible: sheet.model && sheet.model.ranges.length > 1
                width: parent.width; spacing: Theme.grid
                Caption { text: "Range" }
                ChoiceField { width: parent.width; options: sheet.model ? sheet.model.ranges : []
                              current: sheet.model ? sheet.model.range : ""; onPicked: (v) => sheet.model.setRange(v) }
            }
            Column {
                width: parent.width; spacing: Theme.grid
                Caption { text: "Where" }
                Line { text: sheet.model ? sheet.model.fileName : ""; objectName: "exportFileName" }
                Line { text: sheet.model ? sheet.model.where : ""; color: Theme.fg3; font.pixelSize: Theme.label }
                Row {
                    spacing: Theme.gap
                    Button { text: "Browse…"; enabled: !sheet.running
                             onClicked: { if (sheet.model.folder) folderDialog.currentFolder = "file:///" + sheet.model.folder.replace(/\\/g, "/")
                                          folderDialog.open() } }
                    Button { visible: sheet.model && sheet.model.folder !== ""; text: "Renders folder"; kind: "ghost"
                             enabled: !sheet.running; onClicked: sheet.model.setFolder("") }
                }
            }

        }
    }
    Column {        // Export and what it is doing: pinned under the choices, never scrolled out of sight (S36)
        id: footer
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
        topPadding: Theme.gap; spacing: Theme.gap
        Button {
            width: footer.width
            visible: !sheet.running
            text: "Export"; kind: "primary"
            onClicked: sheet.model.request()
        }
        Row {           // while it runs: how far, and Cancel
            visible: sheet.running
            width: footer.width; spacing: Theme.gap
            Rectangle {
                anchors.verticalCenter: parent.verticalCenter
                width: footer.width - (cancelBtn.visible ? cancelBtn.width + Theme.gap : 0); height: 4; radius: 2; color: Theme.raised
                Rectangle { height: parent.height; radius: 2; color: Theme.accent
                            width: sheet.model && sheet.model.progress >= 0 ? parent.width * sheet.model.progress : parent.width / 4
                            opacity: sheet.model && sheet.model.progress >= 0 ? 1 : 0.5 }
            }
            Button { id: cancelBtn; visible: sheet.model && sheet.model.cancellable; text: "Cancel"
                     onClicked: sheet.model.cancel() }
        }
        Text {          // what it is doing, what it made, or what failed (one sentence; the old file is kept)
            visible: sheet.model && sheet.model.state !== "" && text !== ""
            width: footer.width; wrapMode: Text.Wrap
            text: !sheet.model ? "" : sheet.model.state === "failed" ? sheet.model.note.replace(/^Error: [a-z_ ]+: /, "")
                                    : sheet.model.state === "done" && sheet.model.note === sheet.model.doneMessage ? "" : sheet.model.note
            color: sheet.model && sheet.model.state === "failed" ? Theme.danger : Theme.fg2
            font.family: uiFont; font.pixelSize: Theme.body
        }
        Row {           // done: Exported · Play · Show in folder
            visible: sheet.model && sheet.model.state === "done"
            spacing: Theme.gap
            Text { text: "Exported"; color: Theme.ok; font.family: uiFont; font.pixelSize: Theme.body; font.weight: Font.DemiBold
                   height: 16; verticalAlignment: Text.AlignVCenter }
            Link { text: "Play"; onClicked: sheet.model.play() }
            Link { text: "Show in folder"; onClicked: sheet.model.showInFolder() }
        }
    }
    EdgeFade { flick: flick; anchors.fill: flick }   // a half-scrolled row fades (S36 stray check)

    FolderDialog {
        id: folderDialog
        title: "Export into this folder"
        onAccepted: sheet.model.setFolder(selectedFolder.toString())
    }
    Connections {
        target: sheet.model
        function onAsked(name, canReplace) { ask.name = name; ask.canReplace = canReplace; ask.open() }
    }
    QQC.Popup {     // the one blocking question: a file of that name is already there
        id: ask
        objectName: "exportQuestion"
        property string name: ""
        property bool canReplace: true
        function pick(v) { close(); sheet.model.answer(v) }
        parent: QQC.Overlay.overlay
        x: Math.round((parent.width - width) / 2); y: Math.round(parent.height * 0.28)
        width: 440
        padding: Theme.groupGap
        modal: true; focus: true
        closePolicy: QQC.Popup.NoAutoClose
        QQC.Overlay.modal: Rectangle { color: Theme.scrim }
        background: Rectangle { color: Theme.raised; radius: Theme.radiusPanel; border.color: Theme.popupEdge }
        contentItem: FocusScope {
            implicitHeight: askCol.implicitHeight
            Keys.onEscapePressed: ask.pick("cancel")
            Column {
                id: askCol
                width: parent.width; spacing: Theme.pad
                Text { width: parent.width; wrapMode: Text.Wrap; text: "“" + ask.name + "” is already there"
                       color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.heading; font.weight: Font.DemiBold }
                Text { width: parent.width; wrapMode: Text.Wrap; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body
                       text: ask.canReplace ? "Replace it with this export, or keep both (the new one gets a number)."
                                            : "A folder of frames can't be replaced. Keep both (the new one gets a number)?" }
                Row {
                    anchors.right: parent.right; spacing: Theme.gap
                    Button { text: "Cancel"; kind: "ghost"; onClicked: ask.pick("cancel") }
                    Button { text: "Keep both"; kind: ask.canReplace ? "normal" : "primary"; onClicked: ask.pick("both") }
                    Button { visible: ask.canReplace; text: "Replace"; kind: "primary"; danger: true; onClicked: ask.pick("replace") }
                }
            }
        }
    }
}
