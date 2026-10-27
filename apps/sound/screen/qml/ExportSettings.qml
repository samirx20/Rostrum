import QtQuick
import RostrumKit
import "Listening.js" as L

// Sound's part of the kit Export sheet (AppShell.exportSettings; the sheet's What for picker lists the delivery targets,
// screensound/export.py; picking one sets the master's loudness and the sheet says so): the live check of the sound that plays now against the target (pass / miss), the file type,
// stems, and trimming the silent end; "› More" (the sample rate) sits right under File; "+ Another version" adds its rows under
// itself (each its own target, file type and quality, rendered as its own version; the live check under each is that row's
// pass / miss). Nothing a click opens appears above the click: the clicked word and what is above it stay put.
// A delivery preset ("For the Editor", presets.py) is a labelled switch that sets file, quality, trimming, stems and markers; it
// is on while the choices still equal it, and turning it off puts them back to the usual. Picking a target says what it set
// on the master, with Undo beside it while that is still the newest step. When the master cannot reach the target as set, the
// sheet says where the file will land and offers "Push to −14" (the default: Export raises Most limiting) or "Keep it dynamic". Stems: only the mix / every track and group / one per group (only offered
// when the song has a group). "Write the markers beside the files" only when the song has a marker or section.
// What for = MIDI file: a .mid, not a mix, so none of these show (job.isMidi).
Column {
    id: root
    readonly property var job: mixer.export
    readonly property var target: mixer.loudness.target
    width: parent ? parent.width : 0
    spacing: Theme.gap
    property bool more: false          // "More": the sample rate (DESIGN.md §2.4), for the file and each version
    // closed, the live check waits: it is measured again once the sheet shows (a moment after: the news is the exporter's
    // one `changed`, and sent while the sheet's own opening is still being worked out it made AppShell's exportOpen loop)
    onVisibleChanged: Qt.callLater(job.watch, visible)
    Component.onCompleted: job.watch(visible)

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
    component Action: Text {           // a quiet word to click, at the same left edge as the labels
        signal clicked()
        color: actHover.hovered ? Theme.fg : Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body
        height: Theme.rowDense; verticalAlignment: Text.AlignVCenter
        HoverHandler { id: actHover; cursorShape: Qt.PointingHandCursor }
        TapHandler { onTapped: parent.clicked() }
    }

    visible: !job.isMidi
    height: visible ? implicitHeight : 0      // a hidden column keeps its height, which was the hole under the list for MIDI
    Column {   // a solo or mute that is on changes what the file holds: said first, with the one click that fixes it
        objectName: "exportListening"
        readonly property var heard: backend.listening
        readonly property bool any: heard.solo.length > 0 || heard.mute.length > 0
        visible: any
        width: root.width; spacing: Theme.grid
        Text { width: parent.width; wrapMode: Text.WordWrap; visible: parent.heard.solo.length > 0; text: L.soloLine(parent.heard)
               color: Theme.warn; font.family: uiFont; font.pixelSize: Theme.body }
        Text { width: parent.width; wrapMode: Text.WordWrap; visible: parent.heard.mute.length > 0; text: L.muteLine(parent.heard)
               color: Theme.warn; font.family: uiFont; font.pixelSize: Theme.body }
        Action { objectName: "exportHearAll"; text: parent.heard.solo.length > 0 && parent.heard.mute.length > 0 ? "Turn off solo and mute"
                                                   : parent.heard.solo.length > 0 ? "Turn off solo" : "Turn off mute"
                 onClicked: backend.hearAll(parent.heard.solo.length > 0 && parent.heard.mute.length > 0 ? "both"
                                            : parent.heard.solo.length > 0 ? "solo" : "mute") }
    }
    Repeater {   // delivery presets: a labelled switch, on while the sheet's choices equal the preset, off puts them back
        model: root.job.presets
        delegate: Item {
            id: pr
            required property var modelData
            width: root.width; height: sw.height
            SwitchRow {      // the kit's switch line: the words flip it too
                id: sw; wordsAfter: true
                checked: root.job.preset === pr.modelData.value
                label: pr.modelData.label
                onToggled: (on) => root.job.setPreset(pr.modelData.value, on)
            }
            HoverHandler { id: prHover }
            HoverTip { text: pr.modelData.detail; hovered: prHover.hovered }
        }
    }
    Column {   // the verdict and what the target set: its room is kept, so picking a target never moves File, Stems or Export under the pointer
        width: root.width; spacing: Theme.gap
        height: Math.max(implicitHeight, 62, root.job.loudnessWay.shown ? tallest : 0)   // the two lines of the check + the line saying what was set (measured: 2 + 1 lines)
        // while Push / Keep it dynamic shows, the room stays at its tallest: switching between them never moves File or Export
        property real tallest: 0
        onImplicitHeightChanged: tallest = root.job.loudnessWay.shown ? Math.max(tallest, implicitHeight) : 0
        Text {   // the live check: the sound that plays now against the target (only once both exist)
            readonly property var check: root.job.check      // one read per change (each read measures it again)
            width: root.width; wrapMode: Text.WordWrap
            visible: root.target.shown && !!check && !!check.text
            text: check && check.text ? (check.ok ? "✓ " : "") + check.text : ""
            color: check && check.ok ? Theme.ok : Theme.warn
            font.family: uiFont; font.pixelSize: Theme.body
        }
        Column {   // the target can't be reached as the master is set: push to it (the default) or keep the mix dynamic, one click
            objectName: "exportLoudnessWay"
            readonly property var way: root.job.loudnessWay
            visible: root.target.shown && way.shown
            width: root.width; spacing: Theme.grid
            Segmented { objectName: "exportLoudnessWayPick"; options: parent.way.options || []; current: parent.way.current || ""
                        onPicked: (v) => root.job.setLoudnessWay(v) }
            Text { width: parent.width; wrapMode: Text.WordWrap; visible: !!parent.way.said; text: parent.way.said || ""
                   color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label }
        }
        Column {   // a lot of limiting would flatten the loud parts: take the peaks off first (one undo step on the song)
            objectName: "exportTame"
            readonly property var offer: root.job.tameOffer
            visible: root.target.shown && offer.shown
            width: root.width; spacing: Theme.grid
            Action { objectName: "exportTamePeaks"; visible: !parent.offer.busy; text: "Tame the peaks first"
                     font.pixelSize: Theme.body; onClicked: root.job.tamePeaks() }
            Text { width: parent.width; wrapMode: Text.WordWrap; text: parent.offer.said || ""
                   color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label }
        }
        Row {   // a target is the master's own setting: picking one sets the loudness; it says so and takes it back in one click
            width: root.width; spacing: Theme.gap; visible: root.job.loudnessSaid !== ""
            Text { width: parent.width - (undo.visible ? undo.width + Theme.gap : 0); wrapMode: Text.WordWrap
                   text: root.job.loudnessSaid; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label }
            Action { id: undo; visible: root.job.canTakeBack; text: "Undo"; font.pixelSize: Theme.label; onClicked: root.job.takeBack() }
        }
    }
    Field {
        label: "File"
        ChoiceField { width: parent.width; options: root.job.formats; current: root.job.format; onPicked: (v) => root.job.setFormat(v) }
    }
    Item {   // "› More" like every other More: the chevron points down while it is open
        width: root.width; height: Theme.rowDense
        Chevron { id: moreChev; anchors.left: parent.left; anchors.verticalCenter: parent.verticalCenter
                  rotation: root.more ? 0 : -90; color: moreHover.hovered ? Theme.fg : Theme.fg2 }
        Text { anchors { left: moreChev.right; leftMargin: Theme.grid + 2; verticalCenter: parent.verticalCenter }
               text: "More"; color: moreHover.hovered ? Theme.fg : Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body }
        HoverHandler { id: moreHover; cursorShape: Qt.PointingHandCursor }
        TapHandler { onTapped: root.more = !root.more }
    }
    Field {
        visible: root.more
        label: "Quality"; tip: "How finely the sound is stored (sample rate)"
        ChoiceField { width: parent.width; options: root.job.rates; current: root.job.rate; onPicked: (v) => root.job.setRate(v) }
    }
    Action { text: "+ Another version"; onClicked: root.job.addVersion() }
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
                       text: "Another version" + (root.job.more.length > 1 ? " " + (ver.index + 1) : ""); color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body }
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
    Field {
        label: "Stems"; tip: "Separate files for the Editor or a mix elsewhere; they add up to the mix"
        ChoiceField { objectName: "exportStems"; width: parent.width; options: root.job.stemChoices; current: root.job.stemsMode; onPicked: (v) => root.job.setStemsMode(v) }
    }
    SwitchRow { wordsAfter: true; visible: root.job.hasMarkers; checked: root.job.markers; onToggled: (v) => root.job.setMarkers(v)
                label: "Markers file" }
    SwitchRow { wordsAfter: true; checked: root.job.trim; onToggled: (v) => root.job.setTrim(v)
                label: "Cut the silence at the end" }
}
