import QtQuick
import RostrumKit

// Stagger… (UX_SPEC 3.19): the action opens this small popover under its button (or under "⋯" when it is in that menu). "Each starts [2 f] after
// the one before", Order. The bars and keys spread live as the number or the order changes; clicking away keeps it as
// one change, Esc takes it back (backend.stagger, screen2d/stagger.py). Modal, so the click that closes it does
// nothing else.
Popover {
    id: pop
    readonly property var st: backend.stagger
    property bool cancelled: false
    title: "Stagger " + pop.st.what
    modal: true                         // the closing click does nothing else
    focusItem: byField
    onEscaped: cancelled = true         // takes it back
    onAccepted: close()                 // keeps it
    onOpened: cancelled = false
    onClosed: cancelled ? st.cancel() : st.end()
    Connections {   // opened by the action; closed when the stagger ends anywhere else (a key, a step, an undo)
        target: pop.st
        function onOpened() { pop.openBy(["action:layer:stagger", "actionsMore"], (shell.width - pop.width) / 2, 104) }
        function onChanged() { if (!pop.st.open && pop.opened) pop.close() }
    }
    Column {
        spacing: Theme.gap
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
