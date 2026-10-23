import QtQuick
import RostrumKit

// The Library (DESIGN.md §2.2, decision 3; INTERACTION.md "Library", Ctrl+L): adding a track is choosing its sound. A search box (focused on open),
// kind chips (All · Instruments · Drums · Record · Voice · My sounds; the picked one is lit) and the list (adder.find). Click picks an entry;
// double-click or Enter uses it: a new track with that sound (one operation, one undo step), selected, the Editor
// open on it — the microphone's track comes armed, ready to record. With a track of the same kind selected it asks
// "Change Piano to Strings? The notes stay." and changes that track's sound instead (adder.swap, one undo step). "My sounds" is the person's own library
// (LibraryPanel.qml: a sound goes on the selected recordings track at the playhead). Picking an entry (click, ↑ / ↓) plays it
// through the engine (soundLibrary.auditionEntry: an instrument plays the selected track's notes); Esc or ■ Stop ends it. On a track that plays that kind of sound the pick is a try (nothing is written: "Trying Pad
// on Strings"): Enter / double-click / Keep makes it the track's sound (one undo step), Esc / Revert / another track puts the
// original back. Loop (the loop mark beside ▶ on the row that plays) repeats what you hear. Closes with × or Ctrl+L; on a narrow window it floats and closes after each use (`used`).
Panel {
    id: p
    title: "Library"
    signal used()
    property string chip: ""
    property int current: 0
    readonly property string query: search.input.activeFocus ? search.input.text : search.text
    readonly property var found: chip === "mine" ? [] : adder.find(query, chip)
    headerRight: IconButton { glyph: "×"; kind: "ghost"; tip: "Close (Ctrl+L)"; width: Theme.field; height: Theme.field
                              onClicked: workspace.setLibrary(false) }
    onVisibleChanged: if (visible) { search.input.forceActiveFocus(); current = 0 }
    Keys.onEscapePressed: (e) => { if (soundLibrary.swapping) soundLibrary.swapBack(); else if (soundLibrary.auditioning !== "" || soundLibrary.trying.key !== undefined) soundLibrary.revert(); else e.accepted = false }
    Connections { target: workspace; function onChanged() { if (!workspace.library) { soundLibrary.swapBack(); soundLibrary.stopAudition() } } }   // closed: it stops
    Connections { target: backend; function onLibraryWanted(chip) { p.chip = chip } }   // "Place a sound"
    onFoundChanged: current = 0
    // the row of the sound being tried, however the try started (a click, an agent, a step); -1 when none
    readonly property int triedAt: soundLibrary.trying.key === undefined ? -1 : found.findIndex(e => e.key === soundLibrary.trying.key)
    readonly property int shownAt: triedAt >= 0 ? triedAt : current

    function pick(i) {                                   // click or arrow: select it and hear it
        current = i
        const e = found[i]
        if (e && e.kind !== "record") soundLibrary.auditionEntry(e.key)
    }

    function use(i) {
        const e = found[i]
        if (!e) return
        const m = adder.match(e.key)
        if (m.track && soundLibrary.trying.key === e.key) { if (soundLibrary.keep()) p.used(); return }   // a tried sound: Enter keeps it
        if (m.track) { swap.entry = e.key; swap.track = m.track
                       swap.heading = "Change " + m.from + " to " + m.to + "?"; swap.open(); return }
        if (!adder.add(e.key)) return
        if (e.arm) recorder.arm(backend.selected)
        workspace.setDock("editor")
        p.used()
    }

    FieldFrame {
        id: search
        editable: true; placeholder: "Search sounds"
        anchors { left: parent.left; right: parent.right; top: parent.top }
        onCommitted: (t) => search.text = t                // the words stay after Enter
        onArrow: (dir) => p.chip === "mine" ? soundLibrary.swapStep(-dir) : p.pick(Math.max(0, Math.min(p.found.length - 1, p.current - dir)))
        onEscaped: soundLibrary.swapping ? soundLibrary.swapBack() : soundLibrary.stopAudition()
        onEntered: soundLibrary.swapping ? soundLibrary.swapKeep() : p.use(p.current)
    }
    Flow {      // the kinds as chips, one click each, wrapping when narrow; for "My sounds" also the Filter (length, tone, kind of recording)
        id: chips
        anchors { left: parent.left; right: parent.right; top: search.bottom; topMargin: Theme.gap }
        spacing: Theme.grid
        Repeater {
            model: adder.kinds
            delegate: Button { required property var modelData
                               text: modelData.label; height: Theme.button
                               kind: p.chip === modelData.value ? "primary" : "normal"
                               onClicked: p.chip = modelData.value }
        }
        Button { id: filterBtn; visible: p.chip === "mine" && soundLibrary.hasFolders; kind: "ghost"; height: Theme.field
                 text: soundLibrary.filterCount > 0 ? "Filter · " + soundLibrary.filterCount + " ▾" : "Filter ▾"
                 down: mine.filterOpen; onClicked: mine.openFilter(filterBtn) }
    }
    ListView {
        id: list
        visible: p.chip !== "mine"
        anchors { left: parent.left; right: parent.right; top: chips.bottom; bottom: heard.top; topMargin: Theme.gap; bottomMargin: Theme.gap }
        clip: true; spacing: 2; boundsBehavior: Flickable.StopAtBounds
        footer: Item { width: list.width; height: Theme.pad }   // the last row scrolls fully into view
        model: p.found
        currentIndex: p.current
        delegate: Rectangle {
            id: row
            required property var modelData
            required property int index
            width: list.width; height: row.modelData.note !== "" ? 44 : 32; radius: Theme.radiusCtl
            color: p.shownAt === index ? Theme.accentSoft : hover.hovered ? Theme.hover : "transparent"
            HoverHandler { id: hover; cursorShape: Qt.PointingHandCursor }
            TapHandler { onTapped: p.pick(row.index); onDoubleTapped: p.use(row.index) }
            readonly property bool heard: p.shownAt === index && (soundLibrary.auditioning !== "" || p.triedAt >= 0)
            Row {   // ▶ on the row under the pointer and on the one being heard; Loop beside it, only while it plays
                id: hear
                visible: (hover.hovered || row.heard) && row.modelData.kind !== "record"
                anchors { right: parent.right; rightMargin: Theme.grid; verticalCenter: parent.verticalCenter }
                spacing: 2
                IconButton { mark: "loop"; kind: "ghost"; tip: "Repeat what you hear"; visible: row.heard; down: soundLibrary.loop
                             onClicked: soundLibrary.setLoop(!soundLibrary.loop) }
                IconButton { glyph: "▶"; kind: "ghost"; tip: "Hear it"; onClicked: p.pick(row.index) }
            }
            Column {
                anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; leftMargin: Theme.gap; rightMargin: Theme.gap + (hear.visible ? hear.width : 0) }
                spacing: 2
                NameLabel { width: parent.width; text: row.modelData.label }
                Text { id: noteText; visible: row.modelData.note !== ""; width: parent.width; text: row.modelData.note
                       HoverTip { text: noteText.truncated ? noteText.text : ""; hovered: hover.hovered }
                       elide: Text.ElideRight; color: Theme.fg3
                       font.family: uiFont; font.pixelSize: Theme.label }
            }
        }
    }
    EdgeFade { flick: list; anchors.fill: list; visible: list.visible }
    Column {   // the search found nothing
        visible: p.chip !== "mine" && p.found.length === 0
        anchors { left: parent.left; right: parent.right; top: chips.bottom; topMargin: Theme.pad }
        spacing: Theme.gap
        Text { width: parent.width; wrapMode: Text.WordWrap; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.body
               text: "No sound called “" + p.query + "”. Try a shorter word, or add a folder of your sounds." }
    }
    LibraryPanel {
        id: mine
        visible: p.chip === "mine"
        query: p.chip === "mine" ? p.query : ""
        anchors { left: parent.left; right: parent.right; top: chips.bottom; bottom: heard.top; topMargin: Theme.gap; bottomMargin: Theme.gap }
        onUsed: p.used()
    }
    Button {
        id: foot
        anchors { left: parent.left; bottom: parent.bottom }
        text: "Add a folder of my sounds…"; kind: "ghost"
        onClicked: { p.chip = "mine"; mine.addFolder() }
    }
    Item {      // only while something plays or is tried: what it is, and Keep / Revert (or the way to stop it)
        id: heard
        readonly property bool trying: soundLibrary.trying.key !== undefined
        visible: soundLibrary.auditioning !== "" || trying
        height: visible ? heardCol.height : 0
        anchors { left: parent.left; right: parent.right; bottom: foot.top }
        Column {
            id: heardCol
            width: parent.width; spacing: Theme.grid
            Text { width: parent.width; wrapMode: Text.WrapAnywhere
                   text: heard.trying ? "Trying " + soundLibrary.trying.label + " on " + soundLibrary.trying.trackName
                                      : "Hearing " + soundLibrary.auditioning
                   color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label }
            Row { spacing: Theme.grid; layoutDirection: Qt.RightToLeft; width: parent.width
                  Button { visible: !heard.trying; text: "■ Stop"; kind: "ghost"; onClicked: soundLibrary.stopAudition() }
                  Button { visible: heard.trying; text: "Keep"; kind: "primary"; onClicked: { if (soundLibrary.keep()) p.used() } }
                  Button { visible: heard.trying; text: "Revert"; kind: "ghost"; onClicked: soundLibrary.revert() } }
        }
    }
    Prompt {    // a track of the same kind is selected: change its sound (the notes stay), or make a new track
        id: swap
        property string entry: ""
        property string track: ""
        message: "The notes stay. Or add the sound as a new track."
        Button { text: "New track"; kind: "ghost"; onClicked: { swap.close(); if (adder.add(swap.entry)) { workspace.setDock("editor"); p.used() } } }
        Button { text: "Cancel"; kind: "ghost"; onClicked: swap.close() }
        Button { text: "Change"; kind: "primary"; onClicked: { swap.close(); if (adder.swap(swap.entry, swap.track)) p.used() } }
    }
}
