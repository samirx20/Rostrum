import QtQuick
import RostrumKit

// RostrumSound: Instruments | Timeline | Mix. Centre: the page (Timeline: the piano roll of the selection's
// track). Right: the inspector of the selected item on every page. Bottom, full width: the arrangement
// (tall on Timeline, slim elsewhere: the tracks stay in sight so sound is always made in context).
// No left panel yet: no page has a job for one. (leftWidth -gap: the kit puts a gap after the left panel even at
// width 0, so this lines the centre up with the timeline; asked of the kit as a "no left panel" option.)
AppShell {
    id: shell
    bridge: backend
    appName: "RostrumSound"
    documentName: backend.docName
    leftWidth: -Theme.gap
    bottomHeight: backend.page === "timeline" ? 300 : 156
    Behavior on bottomHeight { NumberAnimation { duration: Theme.reveal; easing.type: Theme.revealEasing } }

    Shortcut { sequence: "Space"; onActivated: backend.togglePlay() }
    Shortcut { sequences: [StandardKey.Delete, "Backspace"]; onActivated: backend.removeSelected() }

    tools: [
        Segmented {
            options: [{ value: "instruments", label: "Instruments" }, { value: "timeline", label: "Timeline" },
                      { value: "mix", label: "Mix" }]
            current: backend.page
            onPicked: (v) => backend.setPage(v)
        },
        Item { width: Theme.gap; height: 1 },
        PlayButton { playing: backend.playing; onClicked: backend.togglePlay() },
        SongReadout { anchors.verticalCenter: parent.verticalCenter }
    ]
    centre: [
        InstrumentsPage { anchors.fill: parent; visible: backend.page === "instruments" },
        PianoRoll { anchors.fill: parent; visible: backend.page === "timeline" },
        MixPage { anchors.fill: parent; visible: backend.page === "mix" }
    ]
    right: Inspector { anchors.fill: parent; bridge: backend }
    bottom: Timeline { anchors.fill: parent; slim: backend.page !== "timeline" }
}
