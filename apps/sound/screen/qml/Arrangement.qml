import QtQuick
import QtQuick.Dialogs
import RostrumKit

// The arrangement, always in the middle (DESIGN.md §2.2, INTERACTION.md §1.1): a header strip — + Add, ⏮ ▶, ⟳ (only
// with a time range), Record
// (while a track is armed), the position and tempo · beats · key (click: the tempo / key popover), then at the right
// the picture's switch (while the song has one) and the zoom (− + Fit) — then the Timeline (ruler, sections,
// markers, track headers and lanes, + Track, the Master row last). A new song says what to do first (W1): "Start with
// a sound." with Add a track and Bring in a picture. The picture floats at the top right while it is open.
Rectangle {
    id: a
    property alias headerWidth: timeline.headerWidth
    property bool compact: false                       // a small window: the position and key show short
    readonly property alias picture: corner
    readonly property alias readout: readout
    readonly property bool empty: !backend.tracks.some(r => !r.mix)
    signal addTrack()
    function addFromFile() { fileDialog.open() }
    color: Theme.panel; radius: Theme.radiusPanel; clip: true

    FileDialog {
        id: fileDialog
        title: "Add from a file: a sound, a MIDI file or a video"
        nameFilters: fileIn.filters
        onAccepted: fileIn.add(selectedFile.toString())
    }
    Item {   // the header strip
        id: strip
        anchors { left: parent.left; right: parent.right; top: parent.top; leftMargin: Theme.gap; rightMargin: Theme.gap }
        height: 36
        Row {
            anchors { left: parent.left; verticalCenter: parent.verticalCenter }
            spacing: Theme.grid
            Button {        // + Add: a track with a sound (the Library), a picture to work to, a file
                id: add; text: "+ Add"; down: addMenu.visible; height: Theme.button
                onClicked: addMenu.visible ? addMenu.close() : addMenu.open()
                HintMenu {
                    id: addMenu; width: 240
                    entries: [{ value: "track", label: "Track with a sound…", hint: "Ctrl L" },
                              { value: "picture", label: "Picture to work to…" },
                              { value: "file", label: "From a file…", hint: "Ctrl I" }]
                    onPicked: (v) => v === "track" ? a.addTrack() : v === "file" ? fileDialog.open() : backend.setPictureOpen(true)
                }
            }
            Item { width: Theme.gap; height: 1 }
            IconButton {   // ⏮ to the start, drawn (the font's ⏮ is a colour emoji)
                id: toStart; kind: "ghost"; tip: "To the start (Home)"; anchors.verticalCenter: parent.verticalCenter
                onClicked: backend.setTime(0)
                Rectangle { x: 9; anchors.verticalCenter: parent.verticalCenter; width: 2; height: 10
                            color: toStart.hovered ? Theme.fg : Theme.fg2 }
                Text { x: 10; anchors.verticalCenter: parent.verticalCenter; text: "◀"; font.pixelSize: 11
                       color: toStart.hovered ? Theme.fg : Theme.fg2 }
            }
            PlayButton { playing: backend.playing; onClicked: backend.togglePlay(); anchors.verticalCenter: parent.verticalCenter }
            IconButton {   // ⟳ loop: only while a time range exists (Shift+L)
                visible: backend.timeRange.length === 2; glyph: "⟳"; kind: "ghost"; down: backend.looping
                tip: backend.looping ? "Looping the time range (Shift+L)" : "Loop the time range (Shift+L)"
                anchors.verticalCenter: parent.verticalCenter; onClicked: backend.toggleLoop()
            }
            RecordControls { anchors.verticalCenter: parent.verticalCenter }
            Item { width: Theme.gap; height: 1 }
            SongReadout { id: readout; compact: a.compact; anchors.verticalCenter: parent.verticalCenter }
        }
        Row {
            anchors { right: parent.right; verticalCenter: parent.verticalCenter }
            spacing: 2
            Button { visible: backend.picture !== ""; text: "Picture"; kind: "ghost"; down: backend.pictureOpen
                     height: Theme.field; onClicked: backend.setPictureOpen(!backend.pictureOpen) }
            Item { visible: backend.picture !== ""; width: Theme.gap; height: 1 }
            Text {   // while zoomed in: how far
                visible: !backend.viewFit && !a.compact; anchors.verticalCenter: parent.verticalCenter; rightPadding: Theme.gap
                text: "Zoom " + (Math.round(backend.song.length / backend.viewSpan * 10) / 10) + "×"
                color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label
            }
            IconButton { glyph: "−"; kind: "ghost"; tip: "Zoom out (Ctrl −)"; width: Theme.field; height: Theme.field
                         onClicked: backend.zoomStep(0.8) }
            IconButton { glyph: "+"; kind: "ghost"; tip: "Zoom in (Ctrl +)"; width: Theme.field; height: Theme.field
                         onClicked: backend.zoomStep(1.25) }
            Button { text: "Fit"; kind: "ghost"; down: backend.viewFit; height: Theme.field; onClicked: backend.fitView()
                     HoverTip { text: "Show the whole song (Ctrl 0)"; hovered: parent.hovered } }
        }
    }
    Timeline {
        id: timeline
        anchors { left: parent.left; right: parent.right; top: strip.bottom; bottom: parent.bottom }
        onAddTrack: a.addTrack()
    }
    Column {   // a new song: what to do first
        visible: a.empty
        x: timeline.headerWidth + Theme.gap * 2 + Math.max(0, (a.width - timeline.headerWidth - Theme.gap * 2 - width) / 2)
        y: strip.height + Math.max(60, (a.height - strip.height - height) / 2 - 40)
        width: Math.min(420, a.width - timeline.headerWidth - 4 * Theme.gap)
        spacing: Theme.gap
        Text { width: parent.width; text: "Start with a sound."; color: Theme.fg; horizontalAlignment: Text.AlignHCenter
               font.family: uiFont; font.pixelSize: Theme.heading; font.weight: Font.DemiBold }
        Text { width: parent.width; wrapMode: Text.WordWrap; horizontalAlignment: Text.AlignHCenter
               text: "Pick an instrument, a drum kit, a voice or the microphone. Each sound starts its own track."
               color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.body }
        Row {
            anchors.horizontalCenter: parent.horizontalCenter; spacing: Theme.gap; topPadding: Theme.grid
            Button { text: "Add a track"; kind: "primary"; hint: "Ctrl L"; onClicked: a.addTrack() }
            Button { text: "Bring in a picture"; onClicked: backend.setPictureOpen(true)
                     HoverTip { text: "Already have a film? Show it here and make the sound to it"; hovered: parent.hovered } }
        }
    }
    PictureCorner {
        id: corner
        visible: backend.pictureOpen
        width: Math.min(340, a.width * 0.4); z: 5
        anchors { top: strip.bottom; right: parent.right; rightMargin: Theme.gap }
    }
}
