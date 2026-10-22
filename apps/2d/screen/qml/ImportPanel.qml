import QtQuick
import QtQuick.Dialogs
import RostrumKit

// Import: a file (SVG, PDF page, PSD, image, video) or a Figma frame into the open composition, as one change. Only the
// settings that apply to what was chosen are here (a page for a PDF, text handling for an SVG, key / frame / token for Figma).
// Afterwards: what came in, and the list of what didn't come across. Opened from the top bar's Import action.
Rectangle {
    id: panel
    property var job: backend.importer
    property bool shown: false
    readonly property int labelW: 92
    width: 320
    height: Theme.header + col.implicitHeight + Theme.pad
    visible: shown
    color: Theme.panel; radius: Theme.radiusPanel
    border.color: Theme.popupEdge
    z: 20

    Text {
        anchors { left: parent.left; leftMargin: Theme.pad; top: parent.top }
        height: Theme.header; verticalAlignment: Text.AlignVCenter
        text: "IMPORT"; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.label
        font.weight: Font.DemiBold; font.letterSpacing: 0.4
    }
    FileDialog {
        id: dialog
        title: "Choose a file to import"
        nameFilters: ["Images, video, SVG, PDF, PSD (*.svg *.pdf *.psd *.png *.jpg *.jpeg *.webp *.bmp *.gif *.tif *.tiff *.mp4 *.mov *.webm *.mkv *.m4v *.avi)"]
        onAccepted: job.setFile(selectedFile.toString())
    }
    Column {
        id: col
        anchors { left: parent.left; right: parent.right; top: parent.top; topMargin: Theme.header
                  leftMargin: Theme.pad; rightMargin: Theme.pad }
        spacing: Theme.gap

        Row {
            height: Theme.row; spacing: 0
            Text { width: panel.labelW; height: parent.height; verticalAlignment: Text.AlignVCenter
                   text: "From"; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body }
            ChoiceField {
                anchors.verticalCenter: parent.verticalCenter
                width: col.width - panel.labelW
                options: [{ value: "file", label: "A file" }, { value: "figma", label: "Figma" }]; current: job.source
                onPicked: (v) => job.setSource(v)
            }
        }
        Row {
            visible: job.source === "file"; height: visible ? Theme.row : 0; spacing: Theme.gap
            Text { width: panel.labelW - Theme.gap; height: parent.height; verticalAlignment: Text.AlignVCenter
                   text: "File"; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body }
            Button { anchors.verticalCenter: parent.verticalCenter; text: "Choose…"; onClicked: dialog.open() }
            Text { width: col.width - panel.labelW - 72 - Theme.gap; height: parent.height; verticalAlignment: Text.AlignVCenter
                   text: job.fileName || "none chosen"; elide: Text.ElideMiddle
                   color: job.fileName ? Theme.fg : Theme.fg3; font.family: uiFont; font.pixelSize: Theme.body }
        }
        Row {
            visible: job.kind === "pdf"; height: visible ? Theme.row : 0; spacing: 0
            Text { width: panel.labelW; height: parent.height; verticalAlignment: Text.AlignVCenter
                   text: "Page"; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body }
            NumberField { anchors.verticalCenter: parent.verticalCenter; width: col.width - panel.labelW
                          value: job.page; from: 1; to: 9999; step: 1; onEdited: (v) => job.setPage(v) }
        }
        Row {
            visible: job.kind === "svg"; height: visible ? Theme.row : 0; spacing: 0
            Text { width: panel.labelW; height: parent.height; verticalAlignment: Text.AlignVCenter
                   text: "Text in file"; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body }
            ChoiceField {
                anchors.verticalCenter: parent.verticalCenter; width: col.width - panel.labelW
                options: [{ value: "text", label: "Editable text" }, { value: "outline", label: "Outlines (looks the same)" }]
                current: job.text; onPicked: (v) => job.setText(v)
            }
        }
        Repeater {
            model: job.source === "figma" ? [{ k: "key", label: "File key", hint: "from the file's URL" },
                                             { k: "frame", label: "Frame", hint: "name; the first if empty" },
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
                    Component.onCompleted: if (frow.modelData.k === "token") input.echoMode = TextInput.Password
                    onEdited: (v) => figma[frow.modelData.k] = v
                }
            }
        }
        QtObject { id: figma; property string key: ""; property string frame: ""; property string token: "" }
        Row {   // only for a page that is fitted into the composition (svg, pdf, psd, figma)
            visible: job.canKeepSize; height: visible ? Theme.row : 0; spacing: 0
            Text { width: panel.labelW; height: parent.height; verticalAlignment: Text.AlignVCenter
                   text: "Keep original size"; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body
                   elide: Text.ElideRight }
            Item {
                width: col.width - panel.labelW; height: parent.height
                Toggle { anchors { verticalCenter: parent.verticalCenter; left: parent.left; leftMargin: Theme.gap }
                         checked: job.keepSize
                         enabled: job.state !== "running"; onToggled: (v) => job.setKeepSize(v) }
            }
        }
        Row {
            spacing: Theme.gap
            Button { visible: job.ready && job.state !== "running"; text: "Import"; kind: "primary"
                     onClicked: { if (job.source === "figma") { job.runFigma(figma.key, figma.frame, figma.token); figma.token = "" } else job.run() } }
            Button { visible: job.state === "running"; text: "Cancel"; onClicked: job.cancel() }
            Button { text: "Close"; kind: "ghost"; onClicked: panel.shown = false }
        }
        Rectangle {   // progress
            visible: job.state === "running"
            width: col.width; height: 4; radius: 2; color: Theme.raised
            Rectangle { width: parent.width * job.progress; height: parent.height; radius: 2; color: Theme.accent }
        }
        Text {   // what is happening, the error line, or that it was stopped (neither an error nor a success)
            visible: job.state === "running" || job.state === "failed" || job.state === "cancelled"
            width: col.width; wrapMode: Text.Wrap
            text: job.note; font.family: uiFont; font.pixelSize: Theme.body
            color: job.state === "failed" ? Theme.danger : Theme.fg2
        }
        Column {   // what came in, and what didn't
            visible: job.state === "done"
            width: col.width; spacing: Theme.grid
            Text { text: job.note; width: col.width; wrapMode: Text.Wrap; color: Theme.ok
                   font.family: uiFont; font.pixelSize: Theme.body; font.weight: Font.DemiBold }
            Text { visible: job.report.length > 0; width: col.width; topPadding: Theme.grid
                   text: "Didn't come across (" + job.report.length + ")"; color: Theme.warn
                   font.family: uiFont; font.pixelSize: Theme.label; font.weight: Font.DemiBold }
            Repeater {
                model: job.report
                delegate: Text { required property var modelData; width: col.width; wrapMode: Text.Wrap
                                 text: "· " + modelData; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.label }
            }
            Text { visible: job.report.length === 0; text: "Everything came across."
                   color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label }
        }
    }
}
