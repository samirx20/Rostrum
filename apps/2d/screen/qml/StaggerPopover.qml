import QtQuick
import QtQuick.Controls as QQC
import RostrumKit

// Stagger… (UX_SPEC 3.19): the context bar's action opens this small popover under the bar. "Each starts [2 f] after
// the one before", Order. The bars and keys spread live as the number or the order changes; clicking away keeps it as
// one change, Esc takes it back (backend.stagger, screen2d/stagger.py). Modal, so the click that closes it does
// nothing else.
QQC.Popup {
    id: pop
    readonly property var st: backend.stagger
    property bool cancelled: false
    modal: true; dim: false
    padding: Theme.pad
    closePolicy: QQC.Popup.CloseOnPressOutside
    background: Rectangle { color: Theme.raised; radius: Theme.radiusPanel; border.color: Theme.popupEdge }
    onOpened: cancelled = false
    onClosed: cancelled ? st.cancel() : st.end()
    Connections {   // opened by the action; closed when the stagger ends anywhere else (a key, a step, an undo)
        target: pop.st
        function onOpened() { pop.open() }
        function onChanged() { if (!pop.st.open && pop.opened) pop.close() }
    }
    contentItem: Column {
        spacing: Theme.gap
        Shortcut { sequence: "Escape"; enabled: pop.opened; onActivated: { pop.cancelled = true; pop.close() } }   // takes it back
        Shortcut { sequences: ["Return", "Enter"]; enabled: pop.opened; onActivated: pop.close() }                  // keeps it
        Text { text: "Stagger " + pop.st.what; color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body; font.weight: Font.DemiBold }
        Row {
            spacing: Theme.grid
            Text { anchors.verticalCenter: parent.verticalCenter; text: "Each starts"; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body }
            NumberField {
                id: byField
                anchors.verticalCenter: parent.verticalCenter; width: 64
                value: pop.st.by; from: 0; to: 600; step: 1; unit: " f"
                onEdited: (v) => pop.st.setBy(v)
                onScrubbed: (v) => pop.st.setBy(v)
            }
            Text { anchors.verticalCenter: parent.verticalCenter; text: "after the one before"; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body }
        }
        Row {
            spacing: Theme.grid
            Text { anchors.verticalCenter: parent.verticalCenter; text: "Order"; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body }
            ChoiceField {
                anchors.verticalCenter: parent.verticalCenter; width: 160
                options: pop.st.orders; current: pop.st.order
                onPicked: (v) => pop.st.setOrder(v)
            }
        }
    }
}
