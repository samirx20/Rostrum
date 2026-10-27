import QtQuick
import "."

// The amounts popover (INTERACTION.md 1.2 point 5): ONE per window, for every action with amounts (Humanise ▾,
// Repeat…, Start a bar here…). Its rows are the operation's own parameters as the settings panel's rows
// (rostrum_gui/amounts.py; the session: amounts_page.py, `hub.amounts`), titled "<Action> · <what>". It opens when the
// hub asks (`amountsWanted`: under the ▾, the button or the menu's button that opened it, else at the top of the window).
// Live: every change runs the action again on the original items; resting on a choice in an open list shows it too, and
// closing the list with no pick puts it back (ChoiceField tried / untried → page.tryValue / untry). Enter or a click away keeps it as ONE undo step
// named with the amounts; Esc puts everything back. Each row's control is "amount_<param>"; "Another take" (a seed)
// is "amountsAnotherTake".
//   AmountsPopover { hub: backend.actions }
Popover {
    id: pop
    objectName: "amountsPopover"
    property var hub: null
    readonly property var page: hub ? hub.amounts : null
    title: page ? page.title : ""
    focusItem: keys
    // Ctrl+A waits while it is open: selecting everything behind it changed what the session works on and the click-away
    // rule then kept it as a change nobody asked for (Sound: a click in Repeat, Ctrl+A). A field in it still selects its text.
    ownKeys: ["Enter", "Ctrl+A"]
    onAccepted: close()
    onEscaped: if (page) page.cancel()
    onClosed: if (page && page.live) page.keep()
    Connections {
        target: pop.hub
        ignoreUnknownSignals: true
        function onAmountsWanted(id, names) {
            const ov = pop.parent
            pop.openBy(names, ov ? (ov.width - pop.width) / 2 : 0, 104)
        }
    }
    Item { id: keys; width: 1; height: 1; focus: true }     // holds the keys, so Enter keeps (Popover.accepted)
    Column {
        id: list
        width: 68 * Theme.grid                              // the settings rows' own grid at this width
        Repeater {
            model: pop.page ? pop.page.rows : null
            delegate: InspectorRow {
                objectName: model.row === "param" ? "amount_" + model.id : model.row === "more" ? "amountsMore" : ""
                bridge: pop.page
            }
        }
    }
    Button {
        objectName: "amountsAnotherTake"
        visible: !!pop.page && pop.page.again
        x: list.width - width - Theme.keyGutter             // ends where the fields end
        text: "Another take"
        implicitHeight: Theme.field
        help: "The same amounts, another result"
        onClicked: { pop.page.anotherTake(); keys.forceActiveFocus() }    // Enter then keeps (not another take)
    }
}
