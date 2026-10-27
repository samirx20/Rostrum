import QtQuick
import QtQuick.Controls as QQC
import QtQuick.Dialogs
import "."

// Export (INTERACTION.md 1.19 item 8): a sheet in the right column, in the settings panel's place, so the work stays in
// sight. One heading (Export), then what for (a short list in words, each with its file type) · the chosen one's settings (`settings`: the app
// fills it with kit rows) · range (only when the document has more than everything) · where (the project's Renders
// folder, typed in its box or picked with Browse) · the file's name (a field) · Export. A file already there is never replaced without asking: Replace / Keep
// both / Cancel, the one blocking question. The export runs in the background (the top bar's job chip); done, the
// message line says "Exported Main.mp4 · Play · Show in folder". A failure is red, in words; the old file stays.
// `model`: the app's rostrum_gui.export_sheet.ExportSheet. Esc or × closes it.
Panel {
    id: sheet
    property var model
    readonly property int edge: 20                  // rows end where the settings panel's fields do (the keyframe column's width)
    property alias settings: settingsSlot.data      // the chosen item's settings only (the app's rows)
    property alias summary: summarySlot.data        // what it will come to, pinned just above the button (an app's estimate)
    property alias underRange: underRangeSlot.data  // the app's own range rows, right under the range picker (2D's From / To)
    readonly property bool running: model && model.state === "running"
    // titled by what it is; the chosen item is the list's highlighted row (never said twice), or the model's own `sheetTitle`
    title: model && model.sheetTitle ? model.sheetTitle : "Export"
    focus: visible
    // Esc closes it from anywhere: the window's one Esc (AppShell's EscCloses for Export)
    headerRight: IconButton { glyph: "×"; kind: "ghost"; tip: "Close  Esc"; onClicked: sheet.model.setOpen(false) }

    component Line: Text {                // one line of words, whole: a long name breaks at a space, else anywhere, never cut
        width: parent.width; wrapMode: Text.WrapAtWordBoundaryOrAnywhere
        color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body
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
        anchors { left: parent.left; right: parent.right; top: parent.top }
        height: Math.min(contentHeight, parent.height - footer.height)    // Export follows the rows; pinned once they scroll
        contentHeight: col.height + Theme.pad
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        Column {
            id: col
            width: flick.width - sheet.edge
            spacing: Theme.gap

            Column {        // FIRST, as in every bounce dialog: what part (only when the document has more than "everything": a time range, markers)
                readonly property bool has: !!sheet.model && sheet.model.ranges.length > 1
                visible: has || (!!sheet.model && sheet.model.rangeRoom)     // `rangeRoom`: its place is kept, nothing moves when it arrives
                width: parent.width; spacing: Theme.grid
                height: has ? implicitHeight : Theme.field
                ChoiceField { objectName: "exportRange"; visible: parent.has; width: parent.width; options: sheet.model ? sheet.model.ranges : []
                              current: sheet.model ? sheet.model.range : ""; onPicked: (v) => sheet.model.setRange(v) }
                Column { id: underRangeSlot; width: parent.width; spacing: Theme.grid; visible: parent.has && children.length > 0 }
            }
            ChoiceField {   // an app with a few plain choices (model.choicesPicker): one picker, each option's `detail` under its name
                objectName: "exportTarget"
                visible: !!sheet.model && sheet.model.choicesPicker
                width: parent.width; options: sheet.model ? sheet.model.choices : []
                current: sheet.model ? sheet.model.choice : ""; onPicked: (v) => sheet.model.setChoice(v)
            }
            Column {        // the app's choices, in words, each with its file type (the sheet's title is the one heading)
                visible: !(sheet.model && sheet.model.choicesPicker)
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
                        Rectangle { visible: choiceRow.chosen; width: 3; radius: 1.5; color: Theme.accent
                                    anchors { left: parent.left; top: parent.top; bottom: parent.bottom; topMargin: 4; bottomMargin: 4 } }
                        Text { id: kindText; anchors.right: parent.right; anchors.rightMargin: Theme.gap; anchors.verticalCenter: parent.verticalCenter
                               text: choiceRow.modelData.type || ""; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label }
                        Text { anchors { left: parent.left; leftMargin: Theme.gap; right: kindText.left; rightMargin: Theme.gap
                                         verticalCenter: parent.verticalCenter }
                               text: (choiceRow.chosen ? "✓  " : "") + choiceRow.modelData.label; elide: Text.ElideRight
                               color: choiceRow.chosen ? Theme.fg : Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body
                               font.weight: choiceRow.chosen ? Font.DemiBold : Font.Normal }
                        HoverHandler { id: choiceHover; cursorShape: Qt.PointingHandCursor }
                        TapHandler { onTapped: sheet.model.setChoice(choiceRow.modelData.value) }
                    }
                }
            }
            Column { id: settingsSlot; width: parent.width; spacing: Theme.gap; visible: children.length > 0 }

            Item { width: 1; height: Theme.grid }
            Column {        // where: the file's name, its folder, Browse (they say it; no heading)
                width: parent.width; spacing: Theme.grid
                Line { visible: !(sheet.model && sheet.model.nameable); text: sheet.model ? sheet.model.fileName : ""; objectName: "exportFileName" }
                FieldFrame {     // the file's name: typed here, written as typed (the type stays after it)
                    objectName: "exportFileName"
                    visible: !!sheet.model && sheet.model.nameable
                    width: parent.width; editable: !sheet.running
                    text: sheet.model ? sheet.model.nameStem : ""
                    suffix: sheet.model ? sheet.model.nameExt : ""
                    onCommitted: (t) => sheet.model.setNameStem(t)
                }
                FieldFrame {     // the folder: typed here (Enter keeps it, made if it isn't there; Esc puts the old one back), or Browse
                    id: whereField
                    objectName: "exportFolder"
                    width: parent.width; editable: !sheet.running
                    keepOnRefusal: true            // a folder that can't be made keeps the typing, red, with the reason
                    text: sheet.model ? sheet.model.where : ""
                    atRest: sheet.model ? sheet.model.whereShort : ""     // at rest: the middle left out when long (whole on hover)
                    elide: Text.ElideMiddle
                    onCommitted: (t) => problem = sheet.model.typeFolder(t)
                }
                Row {
                    spacing: Theme.gap; topPadding: Theme.grid
                    Button { text: "Browse…"; enabled: !sheet.running
                             onClicked: { if (sheet.model.folder) folderDialog.currentFolder = "file:///" + sheet.model.folder.replace(/\\/g, "/")
                                          folderDialog.open() } }
                    Button { visible: sheet.model && sheet.model.folder !== ""; text: "Renders folder"
                             enabled: !sheet.running; onClicked: sheet.model.setFolder("") }
                }
            }
        }
    }
    Column {        // Export and what it is doing: right under the rows, never scrolled out of sight (S36)
        id: footer
        anchors { left: parent.left; top: flick.bottom }
        width: parent.width - sheet.edge
        topPadding: Theme.gap; spacing: Theme.gap
        Column { id: summarySlot; width: footer.width; spacing: Theme.gap; visible: children.length > 0 }   // never scrolled away
        Button {
            width: footer.width
            visible: !sheet.running
            text: sheet.model ? sheet.model.actionText : "Export"; kind: "primary"
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
            Text { text: sheet.model ? sheet.model.doneWord : "Exported"; color: Theme.ok; font.family: uiFont; font.pixelSize: Theme.body; font.weight: Font.DemiBold
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
    SmallPopup {     // the one blocking question: a file of that name is already there (Esc: Cancel)
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
        onEscaped: sheet.model.answer("cancel")
        QQC.Overlay.modal: Rectangle { color: Theme.scrim }
        background: Rectangle { color: Theme.raised; radius: Theme.radiusPanel; border.color: Theme.popupEdge }
        contentItem: FocusScope {
            implicitHeight: askCol.implicitHeight
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
