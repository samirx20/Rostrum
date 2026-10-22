import QtQuick
import RostrumKit

// Sound's part of the kit Export sheet (AppShell.exportSettings; the sheet's What for list is the delivery targets,
// screensound/export.py): the live check of the sound that plays now against the target (pass / miss), the file type,
// the quality (sample rate), stems, and trimming the silent end.
Column {
    id: root
    readonly property var job: mixer.export
    readonly property var target: mixer.loudness.target
    width: parent ? parent.width : 0
    spacing: Theme.gap

    component Field: Column {         // a label, its control under it at full width (the sheet is narrow)
        id: field
        property string label: ""
        property string tip: ""
        default property alias control: slot.data
        width: root.width; spacing: Theme.grid
        Text { text: field.label; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body
               HoverHandler { id: capHover }
               HoverTip { text: field.tip; hovered: capHover.hovered } }
        Item { id: slot; width: parent.width; height: Theme.field }
    }
    component Switch: Row {
        property alias checked: sw.checked
        property alias text: words.text
        signal toggled(bool on)
        spacing: Theme.gap
        Toggle { id: sw; anchors.verticalCenter: parent.verticalCenter; onToggled: (v) => parent.toggled(v) }
        Text { id: words; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body; anchors.verticalCenter: parent.verticalCenter }
    }

    Text {   // the live check: the sound that plays now against the target (only once both exist)
        width: root.width; wrapMode: Text.WordWrap
        visible: root.target.shown && !!root.target.verdict && !!root.target.verdict.text
        text: root.target.verdict && root.target.verdict.text ? (root.target.verdict.ok ? "✓ " : "") + root.target.verdict.text : ""
        color: root.target.verdict && root.target.verdict.ok ? Theme.ok : Theme.warn
        font.family: uiFont; font.pixelSize: Theme.body
    }
    Field {
        label: "File"
        ChoiceField { width: parent.width; options: root.job.formats; current: root.job.format; onPicked: (v) => root.job.setFormat(v) }
    }
    Field {
        label: "Quality"; tip: "How finely the sound is stored (sample rate)"
        ChoiceField { width: parent.width; options: root.job.rates; current: root.job.rate; onPicked: (v) => root.job.setRate(v) }
    }
    Switch { checked: root.job.stems; onToggled: (v) => root.job.setStems(v)
             text: root.job.stems ? "Stems: a file for every track and group" : "Stems: off (only the mix)" }
    Switch { checked: root.job.trim; onToggled: (v) => root.job.setTrim(v)
             text: root.job.trim ? "Cut the silence at the end" : "Keep the song's full length" }
}
