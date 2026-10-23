import QtQuick
import RostrumKit

// Rostrum3D. Left: the outliner (scene items, materials, shots). Centre: the live viewport, and over it the last
// render while one is shown. Right: the inspector (the selected thing's field operation, values at the playhead,
// key marks). Bottom, full width: the shot's timeline (frames, playhead, the keys of what moves).
// Top bar: Add (with Duplicate / Delete on the selection), Render (Cycles, the shot's camera, the playhead frame), a job off the GUI thread.
AppShell {
    id: shell
    bridge: backend
    appName: "Rostrum3D"
    helpEntries: guides                 // Help's guides (main.py), in the kit's guide viewer
    documentName: backend.shotInfo.label
    leftWidth: 248
    bottomHeight: Math.min(260, 92 + backend.tracks.length * 26)
    Behavior on bottomHeight { NumberAnimation { duration: Theme.reveal; easing.type: Theme.revealEasing } }

    Shortcut { sequence: "Space"; onActivated: backend.togglePlay() }
    Shortcut { sequence: "Left"; onActivated: backend.setFrame(backend.frame - 1) }
    Shortcut { sequence: "Right"; onActivated: backend.setFrame(backend.frame + 1) }
    Shortcut { sequence: "F12"; onActivated: backend.renderStill() }
    Shortcut { sequence: "Shift+F"; onActivated: viewport.toggleLook() }   // Look: Quick <-> Final
    Shortcut { sequence: "Escape"; enabled: backend.renderJob.state === "done" || backend.renderJob.state === "failed"
               onActivated: backend.renderJob.dismiss() }

    Shortcut { sequence: "Escape"; enabled: backend.renderJob.state === "running"; onActivated: backend.renderJob.cancel() }
    function openAddMenu() { addMenu.open() }
    Shortcut { sequence: "Delete"; enabled: backend.adder.canDelete; onActivated: backend.adder.remove() }
    Shortcut { sequence: "Ctrl+D"; enabled: backend.adder.canDuplicate; onActivated: backend.adder.duplicate() }

    tools: [AddMenu { id: addMenu }, RenderButton {}]
    left: Outliner { anchors.fill: parent }
    centre: [
        Viewport { anchors.fill: parent },
        RenderView { anchors.fill: parent }
    ]
    right: Inspector { anchors.fill: parent; bridge: backend; keyMarks: true }
    bottom: Timeline { anchors.fill: parent; labelWidth: shell.leftWidth - Theme.pad }
}
