import QtQuick
import RostrumKit

// The Library (DESIGN.md §2.2, decision 3; INTERACTION.md "Library", Ctrl+L): adding a track is choosing its sound. A search box (focused on open),
// kind chips (All · Instruments · Drums · Mic and files · Voice · My sounds; the picked one is lit) and the list (adder.find). Click picks an entry and plays it;
// the Add button on its row (or Enter) uses it: a new track with that sound (one operation, one undo step), selected, the Editor
// open on it — the microphone's track comes armed, ready to record. Add always adds: changing a track's sound is the track's own
// Sound ▾ picker, never a question here. "My sounds" is the person's own library
// (LibraryPanel.qml: a sound goes on the selected recordings track at the playhead). Picking an entry (click, ↑ / ↓) plays it
// through the engine (soundLibrary.auditionEntry: an instrument plays a short phrase in the song's key and tempo); Esc or ■ Stop ends it.
// A search that finds nothing names the closest sounds, or the kind chip they are under ("Show Instruments").
// A click plays a short phrase in the song's key and tempo, the same row again stops it; double-click adds. A click only previews: it never changes a track's sound. Loop (the loop mark beside Add on the row that plays) repeats what you hear. A voice row has no preview. Closes with × or Ctrl+L, and after each use (`finish`: the preview stops).
Panel {
    id: p
    title: "Library"
    signal used()
    property string chip: ""
    property int current: 0
    property string noHear: ""                           // why the picked entry has no preview (a voice), said where "Hearing …" shows
    readonly property string query: search.input.activeFocus ? search.input.text : search.text
    readonly property var found: chip === "mine" ? [] : adder.find(query, chip)
    headerRight: IconButton { glyph: "×"; kind: "ghost"; tip: "Close (Ctrl+L)"; width: 28; height: 28
                              onClicked: workspace.setLibrary(false) }
    // opens on All: a chip left on from the last visit hid every other kind (critic r11: "clar" under Drums said "no sound")
    onVisibleChanged: if (visible) { chip = ""; search.input.forceActiveFocus(); current = 0; noHear = "" }
    function back() {                                    // Esc: end a swap or a preview first; with neither, the Library closes
        if (soundLibrary.swapping) soundLibrary.swapBack(); else if (soundLibrary.auditioning !== "") soundLibrary.stopAudition(); else workspace.setLibrary(false)
    }
    EscCloses { when: p.visible; area: p; onAsked: p.back() }   // Esc from anywhere (the window's one Esc, AppShell)
    Connections { target: workspace; function onChanged() { if (!workspace.library) { soundLibrary.swapBack(); soundLibrary.stopAudition() } } }   // closed: it stops
    Connections { target: backend; function onLibraryWanted(chip) { p.chip = chip } }   // "Place a sound"
    onFoundChanged: { current = 0; noHear = "" }
    onChipChanged: noHear = ""
    readonly property int shownAt: current

    function pick(i) {                                   // click or arrow: select it and hear it
        current = i
        const e = found[i]
        noHear = e ? e.noHear : ""
        if (e && e.hearable) soundLibrary.auditionEntry(e.key)
        else if (e) soundLibrary.stopAudition()
    }

    function toggle(i) {                                 // a click on a row: it plays at once (the row lights); the same row again stops it
        if (current === i && soundLibrary.auditioning !== "") { soundLibrary.stopAudition(); return }
        pick(i)
    }

    // after an add: the preview stops; the Library stays open on the same search and list, so the next sound is one
    // click away (critic r11: six tracks took six Ctrl+L); a narrow window's floating Library closes (shell.used)
    function finish() { soundLibrary.stopAudition(); p.used() }

    function use(i) {
        const e = found[i]
        if (!e) return
        workspace.setDock("editor")                     // first: the Mixer, now hidden, makes no strip on this click
        if (!adder.add(e.key)) return
        if (e.arm) recorder.arm(backend.selected)
        finish()
    }

    FieldFrame {
        id: search
        editable: true; placeholder: "Search sounds"
        anchors { left: parent.left; right: parent.right; top: parent.top }
        onCommitted: (t) => search.text = t                // the words stay after Enter
        onArrow: (dir) => p.chip === "mine" ? soundLibrary.swapStep(-dir) : p.pick(Math.max(0, Math.min(p.found.length - 1, p.current - dir)))
        onEscaped: p.back()
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
        readonly property int rowH: 40
        readonly property real room: parent.height - chips.y - chips.height - Theme.gap - (heard.visible ? heard.height + Theme.gap : 0) - (foot.visible ? foot.height + Theme.gap : 0)
        anchors { left: parent.left; right: parent.right; top: chips.bottom; topMargin: Theme.gap }
        height: Math.max(rowH, Math.floor((room + spacing) / (rowH + spacing)) * (rowH + spacing) - spacing)   // whole rows only: the strip never slices one
        clip: true; spacing: 2; boundsBehavior: Flickable.StopAtBounds; snapMode: ListView.SnapToItem
        model: p.found
        currentIndex: p.current
        delegate: Rectangle {
            id: row
            required property var modelData
            required property int index
            width: list.width; height: list.rowH; radius: Theme.radiusCtl
            color: p.shownAt === index ? Theme.accentSoft : hover.hovered ? Theme.hover : "transparent"
            HoverHandler { id: hover; cursorShape: Qt.PointingHandCursor }
            TapHandler { onTapped: p.toggle(row.index); onDoubleTapped: p.use(row.index) }
            readonly property bool heard: p.shownAt === index && soundLibrary.auditioning !== ""
            Rectangle { visible: row.heard; width: 3; radius: 1; color: Theme.accent   // the press is answered at once: this row is the one playing
                        anchors { left: parent.left; top: parent.top; bottom: parent.bottom; topMargin: 6; bottomMargin: 6 } }
            Row {   // Add on every row (the row itself hears it); Loop beside it, only while it plays
                id: hear
                anchors { right: parent.right; rightMargin: Theme.grid; verticalCenter: parent.verticalCenter }
                spacing: 2
                IconButton { mark: "loop"; kind: "ghost"; tip: "Repeat what you hear"; visible: row.heard; down: soundLibrary.loop
                             onClicked: soundLibrary.setLoop(!soundLibrary.loop) }
                Button { text: "Add"; height: Theme.field; onClicked: p.use(row.index) }
            }
            Column {
                anchors { left: parent.left; right: parent.right; top: parent.top; topMargin: 5; leftMargin: Theme.gap; rightMargin: Theme.gap + hear.width }   // names on one line down the list, with or without a note
                spacing: 2
                NameLabel { width: parent.width; text: row.modelData.label }
                Text { id: noteText; width: parent.width; text: row.modelData.note
                       HoverTip { text: noteText.truncated ? noteText.text : ""; hovered: hover.hovered }
                       elide: Text.ElideRight; color: Theme.fg3
                       font.family: uiFont; font.pixelSize: Theme.label }
            }
        }
    }
    EdgeFade { flick: list; anchors.fill: list; visible: list.visible }
    Column {   // the search found nothing: the closest names, or the kind it is under (one click to that chip)
        id: none
        objectName: "libraryNone"
        readonly property var miss: visible ? adder.missed(p.query, p.chip) : ({ say: "", chip: "" })
        visible: p.chip !== "mine" && p.found.length === 0
        anchors { left: parent.left; right: parent.right; top: chips.bottom; topMargin: Theme.pad }
        spacing: Theme.gap
        Text { visible: none.miss.chip === ""; width: parent.width; wrapMode: Text.WordWrap; color: Theme.fg3
               font.family: uiFont; font.pixelSize: Theme.body; text: none.miss.say }
        Button { objectName: "libraryShowKind"; visible: none.miss.chip !== ""; height: Theme.button
                 text: none.miss.say; onClicked: p.chip = none.miss.chip }
    }
    LibraryPanel {
        id: mine
        visible: p.chip === "mine"
        query: p.chip === "mine" ? p.query : ""
        anchors { left: parent.left; right: parent.right; top: chips.bottom; bottom: heard.top; topMargin: Theme.gap; bottomMargin: Theme.gap }
        onUsed: p.finish()
    }
    Button {
        id: foot
        anchors { left: parent.left; bottom: parent.bottom }
        visible: p.chip === "mine" && soundLibrary.hasFolders
        height: visible ? implicitHeight : 0
        text: "Add a folder of my sounds…"; kind: "normal"
        onClicked: { p.chip = "mine"; mine.addFolder() }
    }
    Item {      // only while something plays: what it is, and the way to stop it; or why the picked one has no preview
        id: heard
        objectName: "libraryHeard"
        readonly property string problem: p.noHear !== "" ? p.noHear : soundLibrary.auditioning === "" ? soundLibrary.heardProblem : ""
        visible: soundLibrary.auditioning !== "" || problem !== ""
        height: visible ? heardCol.height : 0
        anchors { left: parent.left; right: parent.right; bottom: foot.top }
        Column {
            id: heardCol
            x: Theme.gap; width: parent.width - 2 * Theme.gap; spacing: Theme.grid
            Text { width: parent.width; wrapMode: Text.Wrap
                   text: heard.problem !== "" ? heard.problem : "Hearing " + soundLibrary.auditioning
                   color: heard.problem !== "" && p.noHear === "" ? Theme.danger : Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label }
            Row { spacing: Theme.grid; layoutDirection: Qt.RightToLeft; width: parent.width
                  Button { visible: heard.problem === ""; text: "■ Stop"; kind: "ghost"; onClicked: soundLibrary.stopAudition() } }
        }
    }
}
