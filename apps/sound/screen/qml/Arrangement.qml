import QtQuick
import QtQuick.Dialogs
import RostrumKit

// The arrangement, always in the middle (DESIGN.md §2.2, INTERACTION.md §1.1): a header strip, every control one height (Theme.field),
// ghost style, the play button the one accent — + Add, ⏮ ▶ loop (always there), Record (always there; Take, the level
// and Record keys join it while a track is armed), the metronome, the position and tempo · beats · key (click: the tempo / key popover), then at the right
// the picture's switch (while the song has one), Grid ▾ and Snap, and the zoom (− + Fit) — then the Timeline (ruler, sections,
// markers, track headers and lanes, + Track, the Master row last). A new song shows one button, Add a track. The picture sits under the last row while it fits there, else docked in its own column at the right: never over a lane.
Rectangle {
    id: a
    objectName: "soundArrangement"              // a press in it makes Ctrl+A the arrangement's (press_area.py)
    property int headerWidth: 224                      // the window's choice (Main.qml); the headers never go under `minHeader`
    // a short row puts R M S A beside the name (TrackHeader): this keeps about eight letters of the name beside them,
    // so a small window shows names, never just "…"
    readonly property int minHeader: 176
    property bool compact: false                       // a small window: the position and key show short
    // the room an open dock (Editor or Mixer) would take but doesn't while folded: the track rows are as tall as with
    // it open, so opening the Editor never changes a row's height or layout (critic r10 must-fix 4: the spot of a
    // track's name became its Solo button once the rows shrank)
    property real dockSlack: 0
    readonly property bool tight: a.width < 860        // a squeezed panel (a drawer open on a small window): − + fold away (Ctrl −/+, Fit stay)
    readonly property alias picture: corner
    readonly property bool empty: !backend.tracks.some(r => !r.mix)
    // the height every row needs at its smallest (header strip, ruler, tracks, + Track, groups, Master): the dock leaves
    // the arrangement this much (up to half the window), so the Master row is never cut off by an open dock. Open
    // automation lanes don't count: one opening must not resize the dock and with it every row (the A just clicked
    // would move under the pointer); the lanes scroll with the rows instead
    readonly property real needs: strip.height + timeline.rulerBottom + Theme.grid + Theme.gap
        + (timeline.rows.length - timeline.mixRows - timeline.groupRows) * 24 + timeline.addH + timeline.mixRows * timeline.mixH
        + timeline.groupRows * timeline.groupH + Math.max(0, timeline.rows.length - 1) * timeline.rowGap
    signal addTrack()
    function addFromFile() { fileDialog.open() }
    function openGrid() { gridBtn.clicked() }          // (the scripted `grid-open` step)
    color: Theme.panel; radius: Theme.radiusPanel; clip: true

    FileDialog {
        id: fileDialog
        title: "Add from a file: a sound, a MIDI file or a video"
        nameFilters: fileIn.filters
        onAccepted: fileIn.add(selectedFile.toString())
    }
    DropArea {   // files dragged in from the desktop or Explorer: each as From a file… takes it (a video: the picture)
        objectName: "arrangementDrop"
        anchors.fill: parent
        keys: ["text/uri-list"]
        onEntered: (drag) => drag.accept(Qt.CopyAction)
        onDropped: (drop) => {
            var took = false
            for (var i = 0; i < drop.urls.length; i++) took = fileIn.add(String(drop.urls[i])) || took
            if (took) drop.accept(Qt.CopyAction)
        }
    }
    Item {   // the header strip
        id: strip
        anchors { left: parent.left; right: parent.right; top: parent.top; leftMargin: Theme.gap; rightMargin: Theme.gap }
        height: 36
        Row {
            id: leftRow
            anchors { left: parent.left; verticalCenter: parent.verticalCenter }
            spacing: Theme.grid
            Button {        // + Add: a track with a sound (the Library), a picture to work to, a file
                id: add; text: "+ Add"; kind: "ghost"; down: addMenu.visible; height: Theme.field
                onClicked: { if (addMenu.visible) { addMenu.close(); return }
                             const p = add.mapToItem(null, 0, add.height + 2); addMenu.openAt(p.x, p.y) }
                ActionMenu {    // the kit's menu with keys
                    id: addMenu
                    entries: [{ value: "track", label: "Track with a sound…", keys: "Ctrl+L" },
                              { value: "picture", label: "Picture to work to…" },
                              { value: "file", label: "From a file…", keys: "Ctrl+I" }]
                    onPicked: (v) => v === "track" ? a.addTrack() : v === "file" ? fileDialog.open() : backend.setPictureOpen(true)
                }
            }
            Item { width: Theme.gap; height: 1 }
            IconButton {   // ⏮ to the start (Home), drawn (the font's ⏮ is a colour emoji)
                id: toStart; visible: !a.tight; kind: "ghost"; tip: "To the start (Home)"; width: Theme.field; height: Theme.field
                anchors.verticalCenter: parent.verticalCenter
                onClicked: backend.setTime(0)
                Rectangle { x: 7; anchors.verticalCenter: parent.verticalCenter; width: 2; height: 10
                            color: toStart.hovered ? Theme.fg : Theme.fg2 }
                Text { x: 8; anchors.verticalCenter: parent.verticalCenter; text: "◀"; font.pixelSize: 11
                       color: toStart.hovered ? Theme.fg : Theme.fg2 }
            }
            PlayButton {   // play / stop (Space): the strip's one accent
                primary: true; playing: backend.playing; onClicked: backend.togglePlay()
                width: Theme.field; height: Theme.field; anchors.verticalCenter: parent.verticalCenter
            }
            IconButton {   // loop (Shift+L): always there; with no time range it makes one (the selection, else four bars)
                mark: "loop"; kind: "ghost"; down: backend.looping; width: Theme.field; height: Theme.field
                tip: backend.looping ? "Looping (Shift+L): click to stop" : "Loop (Shift+L): the time range, the selection, else four bars from here"
                anchors.verticalCenter: parent.verticalCenter; onClicked: backend.toggleLoop()
            }
            RecordControls { anchors.verticalCenter: parent.verticalCenter }
            IconButton {   // the metronome (Shift+K), on while it is down
                visible: !a.tight; icon: "metronome"; kind: "ghost"; down: backend.clickOn; width: Theme.field; height: Theme.field
                tip: backend.clickOn ? "Metronome click is on (Shift+K)" : "Metronome click (Shift+K)"
                anchors.verticalCenter: parent.verticalCenter; onClicked: backend.toggleClick()
            }
            Item { width: Theme.gap; height: 1 }
            SongReadout { id: readout; room: rightRow.x - leftRow.x - x - Theme.gap; compact: a.compact || a.tight; tight: a.tight; anchors.verticalCenter: parent.verticalCenter }
        }
        Row {
            id: rightRow
            anchors { right: parent.right; verticalCenter: parent.verticalCenter }
            spacing: 2
            Button { visible: backend.picture !== ""; text: "Picture"; kind: "ghost"; down: backend.pictureOpen
                     height: Theme.field; onClicked: backend.setPictureOpen(!backend.pictureOpen) }
            Item { visible: backend.picture !== ""; width: Theme.gap; height: 1 }
            Button {   // Grid ▾: the step every snap uses (timing.GRID; screen state)
                id: gridBtn; kind: "ghost"; height: Theme.field; down: gridMenu.visible
                text: "Grid " + backend.gridLabel; chevron: true
                onClicked: { const p = gridBtn.mapToItem(null, 0, gridBtn.height + 2); gridMenu.openAt(p.x, p.y) }
                HoverTip { text: "The grid notes, clips and ranges snap to (Auto follows the zoom)"; hovered: parent.hovered && !gridMenu.visible }
                ActionMenu { id: gridMenu; entries: backend.gridChoices; onPicked: (v) => backend.setGrid(v) }
            }
            Button { objectName: "snapButton"; text: "Snap"; kind: "ghost"; height: Theme.field; down: backend.snapOn
                     onClicked: backend.setSnap(!backend.snapOn)
                     HoverTip { text: backend.snapOn ? "Snapping is on: clicks and drags land on a marker a few pixels away, else the grid (hold Ctrl for free). Click or Shift+G to turn it off"
                                                     : "Snapping is off: everything moves freely. Click or Shift+G to turn it on"; hovered: parent.hovered } }
            Item { width: Theme.gap; height: 1 }
            Text {   // while zoomed in: how far
                visible: !backend.viewFit && !a.compact && !a.tight; anchors.verticalCenter: parent.verticalCenter; rightPadding: Theme.gap
                text: "Zoom " + (Math.round(backend.song.length / backend.viewSpan * 10) / 10) + "×"
                color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label
            }
            IconButton { visible: !a.tight; glyph: "−"; kind: "ghost"; tip: "Zoom out (Ctrl −)"; width: Theme.field; height: Theme.field
                         onClicked: backend.zoomStep(0.8) }
            IconButton { visible: !a.tight; glyph: "+"; kind: "ghost"; tip: "Zoom in (Ctrl +)"; width: Theme.field; height: Theme.field
                         onClicked: backend.zoomStep(1.25) }
            Button { text: "Fit"; kind: "ghost"; down: backend.viewFit; height: Theme.field; onClicked: backend.fitView()
                     HoverTip { text: "Show the whole song (Ctrl 0)"; hovered: parent.hovered } }
        }
    }
    Timeline {
        id: timeline
        headerWidth: Math.max(a.headerWidth, a.minHeader)
        slack: a.dockSlack
        // the picture docked beside the lanes takes its own column: no bar is ever under it (critic r12 should-fix 9)
        anchors { left: parent.left; right: corner.docked ? corner.left : parent.right; top: strip.bottom; bottom: parent.bottom
                  rightMargin: corner.docked ? Theme.gap : 0 }
        onAddTrack: a.addTrack()
    }
    Button {   // a new song: the one thing to do first (no sentence; the + Add menu has the rest). It opens the Library,
               // so it steps aside while the Library is open (centred, it would slide under the pointer as the Library pushes in)
        visible: a.empty && !workspace.library; text: "Add a track"; kind: "primary"
        x: timeline.headerWidth + Theme.gap * 2 + Math.max(0, (a.width - timeline.headerWidth - Theme.gap * 2 - width) / 2)
        y: strip.height + Math.max(60, (a.height - strip.height - height) / 2 - 40)
        onClicked: a.addTrack()
    }
    PictureCorner {
        id: corner
        visible: backend.pictureOpen
        width: Math.min(340, a.width * 0.4); z: 5
        // Never over a lane, so every bar stays reachable by click (critic r9, r10, r12; PLAN S6): under the last row
        // when it fits there (the empty space a folded dock leaves), else docked in its own column at the right, the
        // lanes narrowing beside it (the ruler and the rows fit the bars into what is left)
        readonly property real under: timeline.y + timeline.rowsBottom + Theme.grid
        readonly property bool fitsUnder: under + height + Theme.gap + 12 <= a.height     // (the slim scrollbar stays clear)
        readonly property bool docked: visible && !fitsUnder
        y: fitsUnder ? under : strip.height
        anchors { right: parent.right; rightMargin: Theme.gap }
    }
}
