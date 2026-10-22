import QtQuick
import RostrumKit

// The Library (DESIGN.md §2.2, decision 3; INTERACTION.md "Library", Ctrl+L): adding a track is choosing its sound. A search box (focused on open),
// kind chips (All · Instruments · Drums · Record · Voice · Designed · My sounds; a designed sound is placed at the playhead on
// the Effects track, tied to a marker the playhead sits on) and the list (adder.find). Click picks an entry;
// double-click or Enter uses it: a new track with that sound (one operation, one undo step), selected, the Editor
// open on it — the microphone's track comes armed, ready to record. With a track of the same kind selected it asks
// "Change Piano to Strings? The notes stay." and changes that track's sound instead (adder.swap, one undo step). "My sounds" is the person's own library
// (LibraryPanel.qml: a sound goes on the selected recordings track at the playhead). Picking an entry (click, ↑ / ↓) plays it
// through the engine (soundLibrary.auditionEntry: an instrument plays the selected track's notes); Esc or ■ Stop ends it. Closes with × or Ctrl+L; on a narrow window it floats and closes after each use (`used`).
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
    Keys.onEscapePressed: (e) => { if (soundLibrary.auditioning !== "") soundLibrary.stopAudition(); else e.accepted = false }
    Connections { target: workspace; function onChanged() { if (!workspace.library) soundLibrary.stopAudition() } }   // closed: it stops
    Connections { target: backend; function onLibraryWanted(chip) { p.chip = chip } }   // "Place a sound here"
    onFoundChanged: current = 0

    function pick(i) {                                   // click or arrow: select it and hear it
        current = i
        const e = found[i]
        if (e && e.kind !== "record") soundLibrary.auditionEntry(e.key)
    }

    function use(i) {
        const e = found[i]
        if (!e) return
        const m = adder.match(e.key)
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
        onArrow: (dir) => p.pick(Math.max(0, Math.min(p.found.length - 1, p.current - dir)))
        onEscaped: soundLibrary.stopAudition()
        onEntered: p.use(p.current)
    }
    Flow {
        id: chips
        anchors { left: parent.left; right: parent.right; top: search.bottom; topMargin: Theme.gap }
        spacing: Theme.grid
        Repeater {
            model: adder.kinds
            delegate: Button {
                required property var modelData
                text: modelData.label; kind: "ghost"; height: 24; down: p.chip === modelData.value
                onClicked: p.chip = modelData.value
            }
        }
    }
    ListView {
        id: list
        visible: p.chip !== "mine"
        anchors { left: parent.left; right: parent.right; top: chips.bottom; bottom: heard.top; topMargin: Theme.gap; bottomMargin: Theme.gap }
        clip: true; spacing: 2; boundsBehavior: Flickable.StopAtBounds
        model: p.found
        currentIndex: p.current
        delegate: Rectangle {
            id: row
            required property var modelData
            required property int index
            width: list.width; height: 44; radius: Theme.radiusCtl
            color: p.current === index ? Theme.accentSoft : hover.hovered ? Theme.hover : "transparent"
            HoverHandler { id: hover; cursorShape: Qt.PointingHandCursor }
            TapHandler { onTapped: p.pick(row.index); onDoubleTapped: p.use(row.index) }
            Column {
                anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; leftMargin: Theme.gap; rightMargin: Theme.gap }
                spacing: 2
                Text { width: parent.width; text: row.modelData.label; elide: Text.ElideRight; color: Theme.fg
                       font.family: uiFont; font.pixelSize: Theme.body }
                Text { width: parent.width; text: row.modelData.what; elide: Text.ElideRight; color: Theme.fg3
                       font.family: uiFont; font.pixelSize: Theme.label }
            }
        }
    }
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
    Item {      // only while something plays: what it is, and the way to stop it
        id: heard
        visible: soundLibrary.auditioning !== ""
        height: visible ? Theme.field : 0
        anchors { left: parent.left; right: parent.right; bottom: foot.top }
        Text { anchors { left: parent.left; right: stop.left; rightMargin: Theme.gap; verticalCenter: parent.verticalCenter }
               text: "Hearing " + soundLibrary.auditioning; elide: Text.ElideRight; color: Theme.fg3
               font.family: uiFont; font.pixelSize: Theme.label }
        Button { id: stop; anchors { right: parent.right; verticalCenter: parent.verticalCenter }
                 text: "■ Stop"; kind: "ghost"; onClicked: soundLibrary.stopAudition() }
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
