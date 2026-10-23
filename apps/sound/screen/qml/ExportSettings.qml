import QtQuick
import RostrumKit

// Sound's part of the kit Export sheet (AppShell.exportSettings; the sheet's What for list is the delivery targets,
// screensound/export.py): the live check of the sound that plays now against the target (pass / miss), the file type,
// stems, and trimming the silent end; then "+ Another version" rows (each its own target,
// file type and quality, rendered as its own version; the live check under each is that row's pass / miss).
// A delivery preset ("For the Editor", presets.py) is one button that sets file, quality, trimming, stems and markers; it
// shows as chosen while the choices still equal it. Stems: only the mix / every track and group / one per group (only offered
// when the song has a group). "Write the markers beside the files" only when the song has a marker or section.
// What for = MIDI file: a .mid, not a mix, so none of these show (job.isMidi).
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

    component Action: Text {           // a quiet word to click, at the same left edge as the labels
        signal clicked()
        color: actHover.hovered ? Theme.fg : Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body
        height: Theme.rowDense; verticalAlignment: Text.AlignVCenter
        HoverHandler { id: actHover; cursorShape: Qt.PointingHandCursor }
        TapHandler { onTapped: parent.clicked() }
    }

    visible: !job.isMidi
    height: visible ? implicitHeight : 0      // a hidden column keeps its height, which was the hole under the list for MIDI
    Repeater {   // delivery presets: a row like the sheet's list rows, chosen while the sheet matches it
        model: root.job.presets
        delegate: Rectangle {
            id: pr
            required property var modelData
            readonly property bool chosen: root.job.preset === modelData.value
            width: root.width; height: Theme.rowDense; radius: Theme.radiusCtl
            color: chosen ? Theme.accentSoft : prHover.hovered ? Theme.hover : "transparent"
            Text { anchors { left: parent.left; leftMargin: Theme.gap; verticalCenter: parent.verticalCenter }
                   text: pr.modelData.label; color: pr.chosen ? Theme.fg : Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body }
            HoverHandler { id: prHover; cursorShape: Qt.PointingHandCursor }
            TapHandler { onTapped: root.job.usePreset(pr.modelData.value) }
            HoverTip { text: pr.modelData.detail; hovered: prHover.hovered }
        }
    }
    Text {   // the live check: the sound that plays now against the target (only once both exist)
        width: root.width; wrapMode: Text.WordWrap
        visible: root.target.shown && !!root.job.check && !!root.job.check.text
        text: root.job.check && root.job.check.text ? (root.job.check.ok ? "✓ " : "") + root.job.check.text : ""
        color: root.job.check && root.job.check.ok ? Theme.ok : Theme.warn
        font.family: uiFont; font.pixelSize: Theme.body
    }
    Text {   // no target chosen (the master's numbers match none): said, so the list above is not read as unanswered
        width: root.width; wrapMode: Text.WordWrap; visible: mixer.export.choice === ""
        text: "No target chosen: the mix is exported as it plays now."
        color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label
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
                IconButton { glyph: "×"; kind: "ghost"; tip: "Take this version out"; onClicked: root.job.removeVersion(ver.index) }
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
    Action { text: "+ Another version"; onClicked: root.job.addVersion() }
    Field {
        label: "Stems"; tip: "Separate files for the Editor or a mix elsewhere; they add up to the mix"
        ChoiceField { width: parent.width; options: root.job.stemChoices; current: root.job.stemsMode; onPicked: (v) => root.job.setStemsMode(v) }
    }
    Switch { visible: root.job.hasMarkers; checked: root.job.markers; onToggled: (v) => root.job.setMarkers(v)
             text: "Markers file" }
    Switch { checked: root.job.trim; onToggled: (v) => root.job.setTrim(v)
             text: "Cut the silence at the end" }
    Item {   // "› More" like every other More: the chevron points down while it is open
        width: root.width; height: Theme.rowDense
        Chevron { id: moreChev; anchors.left: parent.left; anchors.verticalCenter: parent.verticalCenter
                  rotation: root.more ? 0 : -90; color: moreHover.hovered ? Theme.fg : Theme.fg2 }
        Text { anchors { left: moreChev.right; leftMargin: Theme.grid + 2; verticalCenter: parent.verticalCenter }
               text: "More"; color: moreHover.hovered ? Theme.fg : Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body }
        HoverHandler { id: moreHover; cursorShape: Qt.PointingHandCursor }
        TapHandler { onTapped: root.more = !root.more }
    }
}
