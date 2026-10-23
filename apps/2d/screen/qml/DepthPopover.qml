import QtQuick
import RostrumKit

// Set depth ▾ › Other depth… (UX_SPEC 3.8, painted backgrounds at depths): a typed camera depth for the selected
// drawings, under the Set depth button. They move back and are resized live while the number changes; clicking away
// or Enter keeps it as one change, Esc takes it back (backend.depthTyped, screen2d/depth_typed.py). Modal, so the
// closing click does nothing else.
Popover {
    id: pop
    readonly property var dt: backend.depthTyped
    property bool cancelled: false
    title: "Depth of " + pop.dt.what
    modal: true
    focusItem: field
    onEscaped: cancelled = true         // takes it back
    onAccepted: close()                 // keeps it
    onOpened: cancelled = false
    onClosed: cancelled ? dt.cancel() : dt.end()
    Connections {   // opened by the action; closed when the depth ends anywhere else (a step, an undo)
        target: pop.dt
        function onOpened() { pop.openBy(["actionBar:Set depth", "actionsMore"], (shell.width - pop.width) / 2, 104) }
        function onChanged() { if (!pop.dt.open && pop.opened) pop.close() }
    }
    Column {
        spacing: Theme.grid
        NumberField {
            id: field
            width: 160
            value: pop.dt.value; from: pop.dt.low; to: pop.dt.high; step: 0.05
            onEdited: (v) => pop.dt.setValue(v)
            onScrubbed: (v) => pop.dt.setValue(v)
        }
        Text { text: "0 = on the camera's plane, higher = farther"; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.label }
    }
}
