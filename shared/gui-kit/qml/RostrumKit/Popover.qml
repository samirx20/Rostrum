import QtQuick
import QtQuick.Controls as QQC
import "."

// A small panel anchored to something, for a few settings that belong to one action (2D's Stagger…, Sound's Land a bar).
//   Popover { id: pop; title: "Stagger 3 layers"; focusItem: byField
//             NumberField { id: byField … }  Row { … } }       // children go in the content slot, under the title
//   pop.openAt(button)            // under `button`, left edges together; above it when there is no room below; a button in the
//                                 // settings panel (`popupsBeside`) near the window's edge: beside that panel, never over its labels
//   pop.openAtPoint(x, y)         // at a point in window coordinates
//   pop.openBy(["action:layer:stagger", "actionsMore"], x, y)   // under the first of these (objectNames) on screen: the button
//                                 // or menu that opened it; at (x, y) when none is shown (a key or a script opened it)
// Built on SmallPopup (the window's keys keep working). Closes on Esc (first `escaped()`, so an app can take the change back;
// typing in a field is dropped with it) and on a click outside. A `modal` popover
// swallows the click that closes it (and never dims the window: `dim` is off). `accepted()` is Enter pressed while it is open, wherever the keyboard is, that no field or list used (the app decides
// whether that closes it: pop.close()). The popover stays inside the window, whatever the size. Keyboard focus goes
// into `focusItem` (else the popover itself) on opening, a field ready to type without a caret (FieldFrame.typeToStart),
// and goes back to what had it when it closes.
SmallPopup {
    id: pop
    property string title: ""
    property Item focusItem: null                 // takes the keys on opening
    default property alias content: slot.data
    signal accepted()

    property var anchor: null                     // what openAt placed it by: placed again when its size settles
    property point point: Qt.point(0, 0)          // or the point openAtPoint was given
    property Item before: null                    // what had the keys before it opened
    ownKeys: ["Enter"]                            // its `accepted()`: the window's Enter waits while it is open

    parent: QQC.Overlay.overlay
    padding: Theme.pad
    margins: Theme.grid                           // grows while open (More): Qt keeps it inside the window, it never moves otherwise
    focus: true
    dim: false                                      // a small popover is light: even a modal one never dims the window
    background: MenuBackground { radius: Theme.radiusPanel }
    // its motion is SmallPopup's: from its anchor's side (`shiftY`, set by place(): from below when it opens above)

    function openAt(item) { anchor = item; place(); open() }
    function openAtPoint(px, py) { anchor = null; point = Qt.point(px, py); place(); open() }
    function openBy(names, px, py) {
        const root = parent && parent.Window.window ? parent.Window.window.contentItem : null
        for (const n of names) {
            const it = root ? shown(root, n) : null
            if (it) { openAt(it); return }
        }
        openAtPoint(px, py)
    }
    function shown(item, name) {          // the visible item called `name` under `item` (depth first), or null
        if (!item.visible) return null
        if (item.objectName === name && item.width > 0) return item
        for (const c of item.children) { const f = shown(c, name); if (f) return f }
        return null
    }
    function place() {
        const ov = parent
        if (!ov) return
        settle()
        shiftX = 0
        let p = anchor ? anchor.mapToItem(ov, 0, anchor.height + Theme.grid) : point
        let y0 = p.y
        shiftY = Theme.popupShift
        if (y0 + height > ov.height - Theme.grid && anchor) {    // no room below: above the anchor
            y0 = anchor.mapToItem(ov, 0, 0).y - height - Theme.grid
            shiftY = -Theme.popupShift
        }
        let x0 = p.x
        if (anchor && x0 + width > ov.width - Theme.grid) {      // it would slide left over the settings panel's labels under
            for (let it = anchor.parent; it; it = it.parent) if (it.popupsBeside === true) {     // its button: beside the panel instead
                const s = it.mapToItem(ov, 0, 0)
                x0 = s.x - width - Theme.gap
                y0 = anchor.mapToItem(ov, 0, 0).y
                shiftY = 0; shiftX = -Theme.popupShift                  // beside the panel: from its side
                break
            }
        }
        x = Math.max(Theme.grid, Math.min(x0, ov.width - width - Theme.grid))
        y = Math.max(Theme.grid, Math.min(y0, ov.height - height - Theme.grid))
    }
    Connections {       // the window resized while open: placed again, so it stays inside and by its anchor (it never moves otherwise)
        target: pop.parent
        function onWidthChanged() { if (pop.visible) pop.place() }
        function onHeightChanged() { if (pop.visible) pop.place() }
    }

    readonly property var focused: parent && parent.Window.window ? parent.Window.window.activeFocusItem : null
    readonly property bool typing: !!focused && focused.cursorPosition !== undefined     // a text field has the keys: it takes Enter first
    readonly property bool mine: {      // the keys are inside this popover (not in a list that opened from it)
        for (let o = focused; o; o = o.parent) if (o === pop.contentItem) return true
        return false
    }
    onAboutToShow: before = focused
    // A field (FieldFrame) takes the keys ready to type, without a caret: a digit starts the number, and Ctrl+G, Delete or
    // a tool key still reach the window, the same the first time and every time after (critic 2d-r11: the first opening
    // put the caret in, where the window's keys wait, so Ctrl+G did nothing; from the second on it did not).
    function takeKeys() {
        const it = focusItem ? focusItem : pop
        if (it.typeToStart !== undefined) { it.typeToStart = true; it.input.focus = false }
        it.forceActiveFocus()
    }
    onOpened: takeKeys()
    onClosed: { if (before && before.visible) before.forceActiveFocus(); before = null }
    // Enter keeps it wherever the keyboard is while it is the newest popup open (critic r10: a choice list picked with the
    // mouse hands the keys to the window behind as it closes, and an Enter that asked `mine` was then heard by nothing).
    // A text field (its own Enter sets its number first) and a list open over it (its Enter picks) go first.
    readonly property bool newest: OpenPopups.open.length > 0 && OpenPopups.open[OpenPopups.open.length - 1] === pop
    KeyShortcut { sequences: ["Return", "Enter"]; enabled: pop.opened && pop.newest && !pop.typing; onActivated: pop.accepted() }

    contentItem: Column {
        readonly property var popover: pop           // a choice list inside finds its popover by this (ChoiceField.handKeysBack)
        spacing: Theme.gap
        // the same Enter as a key press reaching the popover: a background window (app.background()) is never the
        // active one, so its window Shortcut above never fires there; the key itself still comes to the focused row
        Keys.onReturnPressed: (e) => { e.accepted = pop.mine && !pop.typing; if (e.accepted) pop.accepted() }
        Keys.onEnterPressed: (e) => { e.accepted = pop.mine && !pop.typing; if (e.accepted) pop.accepted() }
        NameLabel { visible: pop.title !== ""; text: pop.title; font.weight: Font.DemiBold      // a long title shortens, whole on hover
                    width: Math.min(implicitWidth, 360) }
        Column { id: slot; spacing: Theme.gap }
    }
}
