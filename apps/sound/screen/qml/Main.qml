import QtQuick
import RostrumKit

// RostrumSound: Instruments | Timeline | Mix. Centre: the page (Timeline: the piano roll of the selection's
// track). Right: the inspector of the selected item on every page. Bottom, full width: the arrangement
// (tall on Timeline, slim elsewhere: the tracks stay in sight so sound is always made in context).
// No left panel yet: no page has a job for one.
AppShell {
    id: shell
    bridge: backend
    appName: "RostrumSound"
    documentName: backend.docName
    leftWidth: 0
    bottomHeight: backend.page === "timeline" ? 300 + Math.min(2, backend.tracks.filter(r => r.auto).length) * 78 : 156
    Behavior on bottomHeight { NumberAnimation { duration: Theme.reveal; easing.type: Theme.revealEasing } }

    function openSong() { readout.open() }      // (the scripted `song-open` step)
    function openPicturePick() { backend.setPictureOpen(true); picture.openItems() }     // (`picture-pick`)
    Shortcut { sequence: "Space"; onActivated: backend.togglePlay() }
    Shortcut { sequence: "R"; enabled: recorder.armed !== ""; onActivated: recorder.toggleRecord() }
    Shortcut { sequences: [StandardKey.Delete, "Backspace"]; onActivated: backend.removeSelected() }
    Shortcut { sequences: ["Ctrl+=", "Ctrl++"]; onActivated: backend.zoomStep(1.25) }      // timeline zoom (screen state)
    Shortcut { sequence: "Ctrl+-"; onActivated: backend.zoomStep(0.8) }
    Shortcut { sequences: ["Ctrl+0", "Ctrl+9"]; onActivated: backend.fitView() }                  // show the whole song

    tools: [
        Segmented {
            options: [{ value: "instruments", label: "Instruments" }, { value: "timeline", label: "Timeline" },
                      { value: "mix", label: "Mix" }]
            current: backend.page
            onPicked: (v) => backend.setPage(v)
        },
        Item { width: Theme.gap; height: 1 },
        PlayButton { playing: backend.playing; onClicked: backend.togglePlay() },
        RecordControls { anchors.verticalCenter: parent.verticalCenter },
        SongReadout { id: readout; anchors.verticalCenter: parent.verticalCenter }
    ]
    centre: [
        InstrumentsPage { anchors.fill: parent; visible: backend.page === "instruments" },
        PianoRoll { anchors { fill: parent; rightMargin: picture.visible ? picture.width + Theme.gap : 0 }
                    visible: backend.page === "timeline" },
        PictureCorner { id: picture; width: 340; anchors { top: parent.top; right: parent.right }
                        visible: backend.page === "timeline" && backend.pictureOpen },
        MixPage { anchors.fill: parent; visible: backend.page === "mix" }
    ]
    right: Item {
        anchors.fill: parent
        Inspector { anchors { left: parent.left; right: parent.right; top: parent.top; bottom: clean.top
                              bottomMargin: clean.visible ? Theme.gap : 0 } bridge: backend }
        CleanTakeBar { id: clean; anchors { left: parent.left; right: parent.right; bottom: parent.bottom } height: implicitHeight }
    }
    bottom: Timeline { anchors.fill: parent; slim: backend.page !== "timeline" }
}
