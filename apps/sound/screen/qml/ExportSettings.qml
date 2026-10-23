import QtQuick
import RostrumKit

// Sound's part of the kit Export sheet (AppShell.exportSettings; the sheet's What for list is the delivery targets,
// screensound/export.py): the live check of the sound that plays now against the target (pass / miss), the file type,
// stems, and trimming the silent end; then "+ Another version" rows (each its own target,
// file type and quality, rendered as its own version; the live check under each is that row's pass / miss).
// A delivery preset ("For the Editor", presets.py) is one button that sets file, quality, trimming, stems and markers; it
// shows as chosen while the choices still equal it. Stems: only the mix / every track and group / one per group (only offered
// when the song has a group). "Write the markers beside the files" only when the song has a marker or section.
Column {
    id: root
    readonly property var job: mixer.export
    readonly property var target: mixer.loudness.target
    width: parent ? parent.width : 0
    spacing: Theme.gap
    property bool more: false          // "More": the sample rate (DESIGN.md §2.4), for the file and each version

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
    Repeater {   // delivery presets: one button each, chosen while the sheet matches it
        model: root.job.presets
        delegate: Button {
            required property var modelData
            width: root.width; flushLeft: true; text: modelData.label; kind: root.job.preset === modelData.value ? "primary" : "ghost"
            onClicked: root.job.usePreset(modelData.value)
            HoverHandler { id: presetHover }
            HoverTip { text: modelData.detail; hovered: presetHover.hovered }
        }
    }
    Field {
        label: "File"
        ChoiceField { width: parent.width; options: root.job.formats; current: root.job.format; onPicked: (v) => root.job.setFormat(v) }
    }
    Field {
        visible: root.more
        label: "Quality"; tip: "How finely the sound is stored (sample rate)"
        ChoiceField { width: parent.width; options: root.job.rates; current: root.job.rate; onPicked: (v) => root.job.setRate(v) }
    }
    Repeater {   // "+ Another version": each row is its own target, file type and quality, made as its own version
        model: root.job.more
        delegate: Column {
            id: ver
            required property var modelData
            required property int index
            width: root.width; spacing: Theme.grid
            Row {
                width: parent.width; spacing: Theme.gap
                Text { width: parent.width - Theme.field - Theme.gap; anchors.verticalCenter: parent.verticalCenter
                       text: "Version " + (ver.index + 2); color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body }
                IconButton { glyph: "✕"; kind: "ghost"; tip: "Take this version out"; onClicked: root.job.removeVersion(ver.index) }
            }
            ChoiceField { width: parent.width; options: root.job.targets; current: ver.modelData.target
                          onPicked: (v) => root.job.setVersion(ver.index, "target", v) }
            ChoiceField { width: parent.width; options: root.job.formats; current: ver.modelData.format
                          onPicked: (v) => root.job.setVersion(ver.index, "format", v) }
            ChoiceField { visible: root.more; width: parent.width; options: root.job.ratesFor(ver.modelData.format); current: ver.modelData.rate
                          onPicked: (v) => root.job.setVersion(ver.index, "rate", v) }
            Text { width: parent.width; wrapMode: Text.WordWrap; visible: !!ver.modelData.verdict && !!ver.modelData.verdict.text
                   text: ver.modelData.verdict && ver.modelData.verdict.text ? (ver.modelData.verdict.ok ? "✓ " : "") + ver.modelData.verdict.text : ""
                   color: ver.modelData.verdict && ver.modelData.verdict.ok ? Theme.ok : Theme.warn
                   font.family: uiFont; font.pixelSize: Theme.body }
        }
    }
    Button { text: "+ Another version"; kind: "ghost"; onClicked: root.job.addVersion() }
    Field {
        label: "Stems"; tip: "Separate files for the Editor or a mix elsewhere; they add up to the mix"
        ChoiceField { width: parent.width; options: root.job.stemChoices; current: root.job.stemsMode; onPicked: (v) => root.job.setStemsMode(v) }
    }
    Switch { visible: root.job.hasMarkers; checked: root.job.markers; onToggled: (v) => root.job.setMarkers(v)
             text: "Markers file" }
    Switch { checked: root.job.trim; onToggled: (v) => root.job.setTrim(v)
             text: "Cut the silence at the end" }
    Button { text: root.more ? "Less" : "More"; kind: "ghost"; onClicked: root.more = !root.more }
}
