import QtQuick
import RostrumKit

// The Export sheet (INTERACTION.md §1.19 item 8): it takes the settings panel's place in the right column, so the
// song stays in sight. Where it is going (the target: its loudness and loudest peak in one change, master.set), the
// file, the quality (sample rate), stems, trimming the silent end, the live check of the sound that plays now against
// the target, then Export: the same versioned render as the MCP render_mix (mixer.export, export.py) as a job, then
// "Exported" with Show in folder. A failure stays on the sheet in one sentence. Ctrl+E or the top bar's Export opens
// and closes it (export.dialogOpen); Ctrl+Shift+E exports again with the last settings without opening it.
Panel {
    id: sheet
    readonly property var job: mixer.export
    readonly property var target: mixer.loudness.target
    readonly property bool done: !job.busy && job.folder !== ""
    readonly property bool failed: job.status.indexOf("Error") === 0
    title: "Export"
    headerRight: IconButton { glyph: "×"; kind: "ghost"; tip: "Close (Ctrl+E)"; width: Theme.field; height: Theme.field
                              onClicked: sheet.job.setDialogOpen(false) }

    component Field: Column {         // a label, its control under it at full width (the sheet is narrow)
        id: field
        property string label: ""
        property string tip: ""
        default property alias control: slot.data
        width: parent.width; spacing: Theme.grid
        Text { text: field.label; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body
               HoverHandler { id: capHover }
               HoverTip { text: field.tip; hovered: capHover.hovered } }
        Item { id: slot; width: parent.width; height: Theme.field }
    }

    Flickable {
        anchors.fill: parent; contentHeight: col.height; clip: true; boundsBehavior: Flickable.StopAtBounds
        Column {
            id: col
            width: parent.width; spacing: Theme.pad
            Text { id: songName; width: parent.width; text: backend.docName; elide: Text.ElideMiddle; color: Theme.fg
                   font.family: uiFont; font.pixelSize: Theme.heading; font.weight: Font.DemiBold
                   HoverHandler { id: nameHover }
                   HoverTip { text: songName.truncated ? songName.text : ""; hovered: nameHover.hovered } }
            Field {
                visible: sheet.target.shown
                label: "What for"; tip: "Where it is going: the loudness (LUFS) and loudest peak (dBTP) that place asks for"
                ChoiceField {
                    width: parent.width
                    options: [{ value: "", label: "Choose where it is going…" }].concat(
                        (sheet.target.choices || []).map(c => ({ value: c.id, label: c.label })))
                    current: sheet.target.key || ""
                    onPicked: (v) => { if (v !== "") mixer.loudness.choose(v) }
                }
            }
            Field {
                label: "File"
                ChoiceField { width: parent.width; options: sheet.job.formats; current: sheet.job.format; onPicked: (v) => sheet.job.setFormat(v) }
            }
            Field {
                label: "Quality"; tip: "How finely the sound is stored (sample rate)"
                ChoiceField { width: parent.width; options: sheet.job.rates; current: sheet.job.rate; onPicked: (v) => sheet.job.setRate(v) }
            }
            Row {
                spacing: Theme.gap
                Toggle { checked: sheet.job.stems; onToggled: (v) => sheet.job.setStems(v); anchors.verticalCenter: parent.verticalCenter }
                Text { text: sheet.job.stems ? "Stems: a file for every track and group" : "Stems: off (only the mix)"
                       color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body; anchors.verticalCenter: parent.verticalCenter }
            }
            Row {
                spacing: Theme.gap
                Toggle { checked: sheet.job.trim; onToggled: (v) => sheet.job.setTrim(v); anchors.verticalCenter: parent.verticalCenter }
                Text { text: sheet.job.trim ? "Cut the silence at the end" : "Keep the song's full length"
                       color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body; anchors.verticalCenter: parent.verticalCenter }
            }
            Text {   // the live check: the sound that plays now against the target (only once both exist)
                width: parent.width; wrapMode: Text.WordWrap
                visible: sheet.target.shown && !!sheet.target.verdict && !!sheet.target.verdict.text
                text: sheet.target.verdict && sheet.target.verdict.text ? (sheet.target.verdict.ok ? "✓ " : "") + sheet.target.verdict.text : ""
                color: sheet.target.verdict && sheet.target.verdict.ok ? Theme.ok : Theme.warn
                font.family: uiFont; font.pixelSize: Theme.body
            }
            Text {
                width: parent.width; wrapMode: Text.WordWrap; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label
                text: "Goes into the song's Renders folder, as a new version each time."
            }
            Button {
                width: parent.width
                text: sheet.job.busy ? "Exporting…" : sheet.done ? "Export again" : "Export"
                kind: "primary"; opacity: sheet.job.busy ? 0.6 : 1
                onClicked: if (!sheet.job.busy) sheet.job.start()
            }
            Text {   // what the export is doing, what it made, or why it failed (one sentence)
                visible: text !== ""; width: parent.width; wrapMode: Text.WordWrap
                text: sheet.done ? "Exported · " + sheet.job.status : sheet.job.status.replace(/^Error: render: /, "")
                color: sheet.failed ? Theme.danger : sheet.done ? Theme.ok : Theme.fg2
                font.family: uiFont; font.pixelSize: Theme.body
            }
            Button { visible: sheet.done; text: "Show in folder"; kind: "ghost"; onClicked: sheet.job.reveal() }
        }
    }
}
