import QtQuick
import QtQuick.Controls as QQC
import RostrumKit

// Set depth ▾ › Other depth… (UX_SPEC 3.8, painted backgrounds at depths): a typed camera depth for the selected
// drawings. They move back and are resized live while the number changes; clicking away or Enter keeps it as one
// change, Esc takes it back (backend.depthTyped, screen2d/depth_typed.py). Modal, so the closing click does nothing else.
QQC.Popup {
    id: pop
    readonly property var dt: backend.depthTyped
    property bool cancelled: false
    modal: true; dim: false
    padding: Theme.pad
    closePolicy: QQC.Popup.CloseOnPressOutside
    background: Rectangle { color: Theme.raised; radius: Theme.radiusPanel; border.color: Theme.popupEdge }
    onOpened: cancelled = false
    onClosed: cancelled ? dt.cancel() : dt.end()
    Connections {
        target: pop.dt
        function onOpened() { pop.open() }
        function onChanged() { if (!pop.dt.open && pop.opened) pop.close() }
    }
    contentItem: Column {
        spacing: Theme.gap
        Shortcut { sequence: "Escape"; enabled: pop.opened; onActivated: { pop.cancelled = true; pop.close() } }
        Shortcut { sequences: ["Return", "Enter"]; enabled: pop.opened; onActivated: pop.close() }
        Text { text: "Depth of " + pop.dt.what; color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body; font.weight: Font.DemiBold }
        Row {
            spacing: Theme.grid
            NumberField {
                id: field
                anchors.verticalCenter: parent.verticalCenter; width: 80
                value: pop.dt.value; from: pop.dt.low; to: pop.dt.high; step: 0.05
                onEdited: (v) => pop.dt.setValue(v)
                onScrubbed: (v) => pop.dt.setValue(v)
            }
            Text {
                anchors.verticalCenter: parent.verticalCenter; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label
                text: "0 = on the camera's plane · 1 = moves half as much · higher = farther"
            }
        }
    }
}
