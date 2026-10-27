import QtQuick
import RostrumKit

// 2D's part of the kit Export sheet (AppShell.exportSettings): a typed range's From and To (only for From – to…: they
// sit right under the kit's range picker, `typed`), the scene (only when there is more than one), the
// chosen format's settings (only the ones that apply: backend.exporter.settings, screen2d/export_rows.py; a GIF's ends
// with what it comes to), and after it is done, what the file holds beyond the kit's result line and, for Lottie, what it couldn't carry.
Column {
    id: root
    readonly property var job: backend.exporter
    readonly property int labelW: 92
    width: parent ? parent.width : 0
    spacing: Theme.gap

    component Label: Text {
        width: root.labelW; height: Theme.row; verticalAlignment: Text.AlignVCenter
        color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body; elide: Text.ElideRight
    }
    // From and To of the range From – to…, right under the kit's range picker (the sheet's "exportRange" column; the kit
    // has no place for a range's own rows: kit find for Hem), else first here. One change per typed or dragged value.
    function rangeColumn() {
        let sheet = root.parent
        while (sheet && !("summary" in sheet && "settings" in sheet)) sheet = sheet.parent     // the kit's ExportSheet (its slots)
        const todo = sheet ? [sheet] : []
        while (todo.length) {
            const it = todo.shift()
            if (it.objectName === "exportRange") return it.parent
            for (let i = 0; i < it.children.length; i++) todo.push(it.children[i])
            if (it.contentItem) todo.push(it.contentItem)
        }
        return null
    }
    Column {
        id: typed
        objectName: "exportTypedRange"
        width: root.width
        spacing: Theme.grid
        visible: root.job.typedRange.length > 0
        Component.onCompleted: Qt.callLater(() => { const c = root.rangeColumn(); if (c) typed.parent = c })
        Repeater {
            model: root.job.typedRange
            delegate: Row {
                required property var modelData
                Label { text: modelData.label }
                NumberField { objectName: "exportRange_" + modelData.key; width: 120; anchors.verticalCenter: parent.verticalCenter
                              value: modelData.value; from: 0; step: 0.04; typeStep: 0.001
                              unit: modelData.unit || ""; label: modelData.label
                              onEdited: (v) => root.job.setSetting(modelData.key, v)
                              onScrubbed: (v) => root.job.setSetting(modelData.key, v) }
            }
        }
    }
    Row {
        visible: root.job.comps.length > 0
        Label { text: "Scene" }
        ChoiceField { anchors.verticalCenter: parent.verticalCenter; width: root.width - root.labelW
                      options: root.job.comps; current: root.job.comp; onPicked: (v) => root.job.setComp(v) }
    }
    Repeater {
        model: root.job.settings
        delegate: Row {
            id: srow
            required property var modelData
            readonly property bool wide: modelData.kind === "switch"     // a switch says what it does beside it
            Label { visible: !srow.wide; text: srow.modelData.label }
            Item {      // a note (what a GIF comes to) wraps onto a second line rather than lose its end
                width: srow.wide ? root.width : root.width - root.labelW
                height: srow.modelData.kind === "note" ? Math.max(Theme.row, note.implicitHeight) : Theme.row
                Toggle { visible: srow.modelData.kind === "toggle"; anchors.verticalCenter: parent.verticalCenter
                         checked: !!srow.modelData.value; onToggled: (v) => root.job.setSetting(srow.modelData.key, v) }
                SwitchRow { visible: srow.wide; wordsAfter: true; width: parent.width; label: srow.modelData.label      // the words flip it too
                            checked: !!srow.modelData.value; onToggled: (v) => root.job.setSetting(srow.modelData.key, v) }
                Text { id: note; visible: srow.modelData.kind === "note"; width: parent.width; anchors.verticalCenter: parent.verticalCenter
                       text: srow.modelData.kind === "note" ? srow.modelData.value : ""; color: Theme.fg; wrapMode: Text.Wrap
                       font.family: uiFont; font.pixelSize: Theme.body }
                ChoiceField { visible: srow.modelData.kind === "choice"; anchors.verticalCenter: parent.verticalCenter; width: parent.width
                              options: srow.modelData.options || []; current: String(srow.modelData.value)
                              onPicked: (v) => root.job.setSetting(srow.modelData.key, v) }
            }
        }
    }
    Repeater {          // done: the result, read back from the file
        model: root.job.facts
        delegate: Row {
            required property var modelData
            Text { width: root.labelW; text: modelData.label; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label }
            Text { width: root.width - root.labelW; text: modelData.text.replace(/\\/g, "\\​"); color: Theme.fg; font.family: uiFont
                   font.pixelSize: Theme.label; wrapMode: Text.Wrap; maximumLineCount: 4; elide: Text.ElideMiddle }
        }
    }
    Text { visible: root.job.report.length > 0; width: root.width
           text: "Lottie couldn't carry"; color: Theme.warn; font.family: uiFont; font.pixelSize: Theme.label; font.weight: Font.DemiBold }
    Repeater {
        model: root.job.report
        delegate: Text { required property var modelData; width: root.width; wrapMode: Text.Wrap
                         text: "· " + modelData; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.label }
    }
}
