import QtQuick
import QtQuick.Dialogs
import RostrumKit

// Export: one format choice, the settings that apply to it (from exporter.settings: nothing is placed per format here),
// where the file goes and what it is called (before, during and after), the Export button (Cancel while it runs), then progress, the result read back from the file, "Cancelled", or the error.
// Opened from the top bar's Export action; sits on the canvas beside the inspector. The composition choice is only there when
// the document has more than one.
Rectangle {
    id: panel
    property var job: backend.exporter
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
        text: "EXPORT"; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.label
        font.weight: Font.DemiBold; font.letterSpacing: Theme.capsSpacing
    }
    FileDialog {
        id: saveDialog
        title: "Save the export as"
        fileMode: FileDialog.SaveFile
        options: FileDialog.DontConfirmOverwrite          // the panel asks (below), in its own words
        currentFolder: "file:///" + files.projectsFolder.replace(/[\\]/g, "/")
        onAccepted: job.setTarget(selectedFile.toString())
    }
    AskDialog {
        id: taken
        objectName: "exportQuestion"
        onAnswered: (value) => job.answer(value)
    }
    Connections {
        target: job
        function onTaken(name, canReplace) {
            taken.ask("Replace " + name + "?", "A file with that name is already there.",
                      [{ value: "cancel", label: "Cancel" }, { value: "both", label: "Keep both" }]
                      .concat(canReplace ? [{ value: "replace", label: "Replace", danger: true }] : []))
        }
    }
    Column {
        id: col
        anchors { left: parent.left; right: parent.right; top: parent.top; topMargin: Theme.header
                  leftMargin: Theme.pad; rightMargin: Theme.pad }
        spacing: Theme.gap

        Row {
            visible: job.comps.length > 0; height: visible ? Theme.row : 0; spacing: 0
            Text { width: panel.labelW; height: parent.height; verticalAlignment: Text.AlignVCenter
                   text: "Composition"; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body }
            ChoiceField {
                anchors.verticalCenter: parent.verticalCenter
                width: col.width - panel.labelW
                options: job.comps; current: job.comp
                onPicked: (v) => job.setComp(v)
            }
        }
        Row {
            height: Theme.row; spacing: 0
            Text { width: panel.labelW; height: parent.height; verticalAlignment: Text.AlignVCenter
                   text: "Format"; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body }
            ChoiceField {
                anchors.verticalCenter: parent.verticalCenter
                width: col.width - panel.labelW
                options: job.formats; current: job.format
                onPicked: (v) => job.setFormat(v)
            }
        }
        Row {
            height: Theme.row; spacing: Theme.gap
            Text { width: panel.labelW - Theme.gap; height: parent.height; verticalAlignment: Text.AlignVCenter
                   text: "Save to"; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body }
            Button { anchors.verticalCenter: parent.verticalCenter; text: "Choose…"; enabled: job.state !== "running"
                     onClicked: { saveDialog.currentFile = "file:///" + (job.target || (files.projectsFolder + "/" + job.fileName)).replace(/[\\]/g, "/"); saveDialog.open() } }
            Button { anchors.verticalCenter: parent.verticalCenter; visible: job.target !== ""; text: "Default"; kind: "ghost"
                     onClicked: job.setTarget("") }
        }
        Column {   // where it will go and what it will be called: before it starts, while it runs, and after
            visible: job.state !== "done"
            width: col.width; spacing: 2
            Text { width: parent.width; text: job.fileName; elide: Text.ElideMiddle; color: Theme.fg
                   font.family: uiFont; font.pixelSize: Theme.body }
            Text { width: parent.width; text: "Saved in " + job.destination.replace(/\\/g, "\\\u200b"); wrapMode: Text.Wrap; maximumLineCount: 4
                   elide: Text.ElideMiddle; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label }
        }
        Repeater {
            model: job.settings
            delegate: Row {
                id: srow
                required property var modelData
                height: Theme.row; spacing: 0
                Text { width: panel.labelW; height: parent.height; verticalAlignment: Text.AlignVCenter
                       text: srow.modelData.label; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body }
                Item {
                    width: col.width - panel.labelW; height: parent.height
                    Toggle { visible: srow.modelData.kind === "toggle"; anchors.verticalCenter: parent.verticalCenter
                             checked: !!srow.modelData.value; onToggled: (v) => job.setSetting(srow.modelData.key, v) }
                    ChoiceField { visible: srow.modelData.kind === "choice"; anchors.verticalCenter: parent.verticalCenter; width: parent.width
                                  options: srow.modelData.options || []; current: String(srow.modelData.value)
                                  onPicked: (v) => job.setSetting(srow.modelData.key, v) }
                    NumberField { visible: srow.modelData.kind === "number"; anchors.verticalCenter: parent.verticalCenter; width: parent.width
                                  value: srow.modelData.value; from: srow.modelData.from || 0; to: srow.modelData.to || 0
                                  step: 0.1; unit: srow.modelData.unit || ""
                                  onEdited: (v) => job.setSetting(srow.modelData.key, v) }
                }
            }
        }
        Row {
            spacing: Theme.gap
            Button { visible: job.state !== "running"; text: "Export"; kind: "primary"; onClicked: job.request() }
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
        Column {   // the result, read back from the file
            visible: job.state === "done"
            width: col.width; spacing: Theme.grid
            Text { text: "Done"; color: Theme.ok; font.family: uiFont; font.pixelSize: Theme.body; font.weight: Font.DemiBold }
            Button { text: "Show in folder"; onClicked: job.showInFolder() }
            Repeater {
                model: job.facts
                delegate: Row {
                    required property var modelData
                    width: col.width; spacing: 0
                    Text { id: fl; width: panel.labelW; text: modelData.label; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label }
                    Text { width: col.width - panel.labelW; text: modelData.text.replace(/\\/g, "\\\u200b"); color: Theme.fg; font.family: uiFont
                           font.pixelSize: Theme.label; wrapMode: Text.Wrap; maximumLineCount: 6; elide: Text.ElideMiddle }
                }
            }
            Image {
                visible: job.picture !== ""
                width: col.width; height: visible ? 120 : 0
                source: job.picture; fillMode: Image.PreserveAspectFit; asynchronous: true; cache: false
            }
            Text { visible: job.report.length > 0; width: col.width; topPadding: Theme.grid
                   text: "Lottie couldn't carry"; color: Theme.warn; font.family: uiFont; font.pixelSize: Theme.label; font.weight: Font.DemiBold }
            Repeater {
                model: job.report
                delegate: Text { required property var modelData; width: col.width; wrapMode: Text.Wrap
                                 text: "· " + modelData; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.label }
            }
            Text { visible: job.format === "lottie" && job.report.length === 0; text: "Everything was carried."
                   color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label }
        }
    }
}
