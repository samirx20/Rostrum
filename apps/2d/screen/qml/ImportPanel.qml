import QtQuick
import RostrumKit

// Import: opens only when it has a question: which page of a PDF, a pasted Figma link (key / frame / token), or the list of
// what didn't come across. A file is picked elsewhere (Add from a file…, Ctrl+I) and comes in at once. Only the settings
// that apply are here (a page for a PDF, text handling for an SVG).
// Afterwards the settings go: only what came in and the list of what didn't come across stay (and the panel closes by
// itself when everything came across: the status line says what was imported).
Rectangle {
    id: panel
    // Always `panel.job`, never bare `job`: inside a kit Button / IconButton a bare `job` is the button's own key-map name
    // (a string), so `job.ready` there was always undefined and the Import button never showed.
    property var job: backend.importer
    property bool shown: false
    readonly property bool done: panel.job.state === "done"
    readonly property int labelW: 92
    width: 320
    height: Theme.header + col.implicitHeight + Theme.pad
    visible: shown
    onShownChanged: if (shown && done && panel.job.report.length === 0) panel.job.clearResult()   // opened again: the last result goes (a report it opened for stays)
    Connections {
        target: panel.job
        function onChanged() { if (panel.done && panel.job.report.length === 0) panel.shown = false }
    }
    color: Theme.panel; radius: Theme.radiusPanel
    border.color: Theme.popupEdge
    z: 20

    Text {
        anchors { left: parent.left; leftMargin: Theme.pad; top: parent.top }
        height: Theme.header; verticalAlignment: Text.AlignVCenter
        text: "Import"; color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body; font.weight: Font.DemiBold
    }
    IconButton { anchors { right: parent.right; rightMargin: Theme.gap; top: parent.top; topMargin: (Theme.header - height) / 2 }
                 glyph: "×"; kind: "ghost"; tip: "Close"; onClicked: panel.shown = false }
    Column {
        id: col
        anchors { left: parent.left; right: parent.right; top: parent.top; topMargin: Theme.header
                  leftMargin: Theme.pad; rightMargin: Theme.pad }
        spacing: Theme.gap

        Column {   // the settings: gone once an import is done
            id: settings
            visible: !panel.done; width: col.width; spacing: Theme.gap
        Row {   // the file waiting for its page (a PDF of several pages); a Figma link has its fields below instead
            visible: panel.job.source === "file"; height: visible ? Theme.row : 0; spacing: Theme.gap
            Text { width: panel.labelW - Theme.gap; height: parent.height; verticalAlignment: Text.AlignVCenter
                   text: "File"; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body }
            Text { width: col.width - panel.labelW; height: parent.height; verticalAlignment: Text.AlignVCenter
                   text: panel.job.fileName; elide: Text.ElideMiddle
                   color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body }
        }
        Row {
            visible: panel.job.kind === "pdf"; height: visible ? Theme.row : 0; spacing: 0
            Text { width: panel.labelW; height: parent.height; verticalAlignment: Text.AlignVCenter
                   text: "Page"; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body }
            NumberField { anchors.verticalCenter: parent.verticalCenter; width: col.width - panel.labelW
                          value: panel.job.page; from: 1; to: panel.job.pageCount; step: 1; onEdited: (v) => panel.job.setPage(v) }
        }
        Row {
            visible: panel.job.hasText; height: visible ? Theme.row : 0; spacing: 0
            Text { width: panel.labelW; height: parent.height; verticalAlignment: Text.AlignVCenter
                   text: "Text in file"; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body }
            ChoiceField {
                anchors.verticalCenter: parent.verticalCenter; width: col.width - panel.labelW
                options: [{ value: "text", label: "Editable text" }, { value: "outline", label: "Outlines (looks the same)" }]
                current: panel.job.text; onPicked: (v) => panel.job.setText(v)
            }
        }
        Repeater {
            model: panel.job.source === "figma" ? [{ k: "key", label: "File key", hint: "from the file's URL" },
                                             { k: "frame", label: "Frame", hint: "name or id; the first if empty" },
                                             { k: "token", label: "Token", hint: "your own, not saved" }] : []
            delegate: Row {
                id: frow
                required property var modelData
                height: Theme.row; spacing: 0
                Text { width: panel.labelW; height: parent.height; verticalAlignment: Text.AlignVCenter
                       text: frow.modelData.label; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body }
                TextField {
                    objectName: "figma_" + frow.modelData.k
                    anchors.verticalCenter: parent.verticalCenter; width: col.width - panel.labelW
                    placeholder: frow.modelData.hint
                    value: frow.modelData.k === "key" ? panel.job.figmaKey : frow.modelData.k === "frame" ? panel.job.figmaFrame : ""
                    Component.onCompleted: if (frow.modelData.k === "token") input.echoMode = TextInput.Password
                    onEdited: (v) => figma[frow.modelData.k] = v
                }
            }
        }
        QtObject { id: figma; property string key: panel.job.figmaKey; property string frame: panel.job.figmaFrame; property string token: "" }
        Row {   // only for a page that is fitted into the composition (svg, pdf, psd, figma)
            visible: panel.job.canKeepSize; height: visible ? Theme.row : 0; spacing: 0
            Text { width: panel.labelW; height: parent.height; verticalAlignment: Text.AlignVCenter
                   text: "Keep original size"; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body
                   elide: Text.ElideRight }
            Item {
                width: col.width - panel.labelW; height: parent.height
                Toggle { anchors { verticalCenter: parent.verticalCenter; left: parent.left; leftMargin: Theme.gap }
                         checked: panel.job.keepSize
                         enabled: panel.job.state !== "running"; onToggled: (v) => panel.job.setKeepSize(v) }
            }
        }
        }
        Row {
            visible: (panel.job.ready && !panel.done) || panel.job.state === "running"; spacing: Theme.gap   // (not read off the children: they are only visible once this is)
            Button { visible: panel.job.ready && !panel.done && panel.job.state !== "running"; text: "Import"; kind: "primary"
                     onClicked: { if (panel.job.source === "figma") { panel.job.runFigma(figma.key, figma.frame, figma.token); figma.token = "" } else panel.job.run() } }
            Button { visible: panel.job.state === "running"; text: "Cancel"; onClicked: panel.job.cancel() }
        }
        Rectangle {   // progress
            visible: panel.job.state === "running"
            width: col.width; height: 4; radius: 2; color: Theme.raised
            Rectangle { width: parent.width * panel.job.progress; height: parent.height; radius: 2; color: Theme.accent }
        }
        Text {   // what is happening, the error line, or that it was stopped (neither an error nor a success)
            visible: panel.job.state === "running" || panel.job.state === "failed" || panel.job.state === "cancelled"
            width: col.width; wrapMode: Text.Wrap
            text: panel.job.note; font.family: uiFont; font.pixelSize: Theme.body
            color: panel.job.state === "failed" ? Theme.danger : Theme.fg2
        }
        Column {   // what came in, and what didn't
            visible: panel.job.state === "done"
            width: col.width; spacing: Theme.grid
            Text { text: panel.job.note; width: col.width; wrapMode: Text.Wrap; color: Theme.ok
                   font.family: uiFont; font.pixelSize: Theme.body; font.weight: Font.DemiBold }
            Text { visible: panel.job.report.length > 0; width: col.width; topPadding: Theme.grid
                   text: "Didn't come across (" + panel.job.report.length + ")"; color: Theme.warn
                   font.family: uiFont; font.pixelSize: Theme.label; font.weight: Font.DemiBold }
            Repeater {
                model: panel.job.report
                delegate: Text { required property var modelData; width: col.width; wrapMode: Text.Wrap
                                 text: "· " + modelData; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.label }
            }
            Text { visible: panel.job.report.length === 0; text: "Everything came across."
                   color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label }
        }
    }
}
