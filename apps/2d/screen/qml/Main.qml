import QtQuick
import RostrumKit

// Rostrum2D: Design | Animate. Left: the composition's layers. Centre: the canvas (the engine's frame).
// Right: the inspector (from the selected item's field operation, values at the playhead, key marks).
// Bottom, full width: on Design a slim time bar, on Animate the keyframe timeline.
AppShell {
    id: shell
    bridge: backend
    appName: "Rostrum2D"
    documentName: backend.frameInfo.label
    leftWidth: 248
    bottomHeight: backend.page === "animate" ? 300 : 52
    Behavior on bottomHeight { NumberAnimation { duration: Theme.reveal; easing.type: Theme.revealEasing } }

    Shortcut { sequence: "Space"; onActivated: backend.togglePlay() }

    tools: Segmented {
        options: [{ value: "design", label: "Design" }, { value: "animate", label: "Animate" }]
        current: backend.page
        onPicked: (v) => backend.setPage(v)
    }
    left: LayersPanel { anchors.fill: parent }
    centre: Stage { anchors.fill: parent }
    right: Inspector { anchors.fill: parent; bridge: backend; keyMarks: true }
    bottom: [
        TimeBar { anchors.fill: parent; visible: backend.page === "design" },
        KeyTimeline { anchors.fill: parent; visible: backend.page === "animate"; labelWidth: shell.leftWidth - Theme.pad }
    ]
}
