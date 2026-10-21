import QtQuick
import RostrumKit

// Rostrum2D: Design | Draw | Animate. Left: the composition's layers. Centre: the canvas (the engine's frame).
// Right: the inspector (from the selected item's field operation, values at the playhead, key marks); on Draw the
// brush (the next stroke's settings, from the brush settings' own rules).
// Bottom, full width: on Design a slim time bar, on Draw the drawing's frames, on Animate the keyframe timeline.
AppShell {
    id: shell
    bridge: backend
    appName: "Rostrum2D"
    documentName: backend.frameInfo.label
    leftWidth: 248
    bottomHeight: backend.page === "animate" ? 300 : backend.page === "draw" ? 132 : 52
    Behavior on bottomHeight { NumberAnimation { duration: Theme.reveal; easing.type: Theme.revealEasing } }

    Shortcut { sequence: "Space"; onActivated: backend.togglePlay() }
    Shortcut { sequence: "Alt+Left"; onActivated: painter.goFrame(-1) }       // frame by frame, on the selected drawing
    Shortcut { sequence: "Alt+Right"; onActivated: painter.goFrame(1) }
    Shortcut { sequence: "Alt+N"; onActivated: painter.newFrame(false) }
    Shortcut { sequence: "Alt+Shift+N"; onActivated: painter.newFrame(true) }
    Shortcut { sequence: "Alt+Up"; onActivated: painter.holdBy(1) }
    Shortcut { sequence: "Alt+Down"; onActivated: painter.holdBy(-1) }
    Shortcut { sequence: "Alt+O"; onActivated: painter.setOnion(!painter.onionOn) }

    function setExportOpen(open) { exportPanel.shown = open }

    tools: [
        Segmented {
            options: [{ value: "design", label: "Design" }, { value: "draw", label: "Draw" },
                      { value: "animate", label: "Animate" }]
            current: backend.page
            onPicked: (v) => backend.setPage(v)
        },
        Button { text: "Export"; down: exportPanel.shown; onClicked: exportPanel.shown = !exportPanel.shown }
    ]
    ExportPanel {   // opened by the Export button, under the top bar at the right
        id: exportPanel
        anchors { right: parent.right; rightMargin: Theme.gap; top: parent.top; topMargin: Theme.topBar }
    }
    left: LayersPanel { anchors.fill: parent }
    centre: Stage { anchors.fill: parent }
    right: [
        Inspector { anchors.fill: parent; bridge: backend; keyMarks: true; visible: backend.page !== "draw" },
        Inspector { anchors.fill: parent; bridge: painter; title: "Brush"; visible: backend.page === "draw" }
    ]
    bottom: [
        TimeBar { anchors.fill: parent; visible: backend.page === "design" },
        FrameBar { anchors.fill: parent; visible: backend.page === "draw"; labelWidth: shell.leftWidth - Theme.pad },
        KeyTimeline { anchors.fill: parent; visible: backend.page === "animate"; labelWidth: shell.leftWidth - Theme.pad }
    ]
}
