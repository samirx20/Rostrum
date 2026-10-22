import QtQuick
import RostrumKit

// 2D's part of the kit Export sheet (AppShell.exportSettings): the composition (only when there is more than one), the
// chosen format's settings (only the ones that apply: backend.exporter.settings, screen2d/export_rows.py), and after
// it is done, the result read back from the file and, for Lottie, what it couldn't carry.
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
    Row {
        visible: root.job.comps.length > 0
        Label { text: "Composition" }
        ChoiceField { anchors.verticalCenter: parent.verticalCenter; width: root.width - root.labelW
                      options: root.job.comps; current: root.job.comp; onPicked: (v) => root.job.setComp(v) }
    }
    Repeater {
        model: root.job.settings
        delegate: Row {
            id: srow
            required property var modelData
            Label { text: srow.modelData.label }
            Item {
                width: root.width - root.labelW; height: Theme.row
                Toggle { visible: srow.modelData.kind === "toggle"; anchors.verticalCenter: parent.verticalCenter
                         checked: !!srow.modelData.value; onToggled: (v) => root.job.setSetting(srow.modelData.key, v) }
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
