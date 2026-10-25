import QtQuick
import QtQuick.Controls as QQC
import "."

// The menu of actions (right-click, a button's ▾, the context bar's ⋯). `entries`: [{value, label, keys, group, sub}].
//  - `keys` shows as a muted chip at the right; a thin divider sits wherever `group` changes;
//  - an entry with `sub` (a list of entries) opens a side menu on hover or Right; Left or Esc closes it;
//  - openAt(x, y [, xIfFlipped]) opens at a point in window coordinates and stays on screen (flips left / up);
//  - Up / Down move, Enter picks, Esc closes. Choosing sends picked(value) from the top menu, whatever its depth.
//  - when any entry has `checked`, a fixed left column shows ✓ on the checked ones (the chosen entry), and the
//    highlight opens on it, so the hover and the tick agree;
//  - an entry's `heading` is a small title drawn once above it, for a set of choices that would otherwise repeat a
//    label on every row ("After the last key" over Stay, Repeat …; F5, audit 44/45);
//  - every row is named "menu:" + its value, so a scripted walk clicks it (clickobj), as in Menu.qml;
// Long labels shorten with "…" and show whole on hover. Width fits the longest label + key (180 to 320).
SmallPopup {
    id: menu
    ownKeys: ["Up", "Down", "Enter", "Left", "Right"]   // the window's shortcuts for these wait while it is open (OpenPopups)
    property var entries: []
    property int highlighted: 0
    property var owner: null                 // the menu this one is a side menu of
    readonly property int dividerHeight: 8
    readonly property int headingHeight: 22
    readonly property bool checks: entries.some(e => e.checked !== undefined)   // reserve the ✓ column
    readonly property int checkW: checks ? 18 : 0
    signal picked(string value)
    signal rested(string value)              // the pointer is on an entry ("" when it left or the menu closed): a hover preview follows it

    parent: QQC.Overlay.overlay
    padding: Theme.grid
    focus: true
    width: Math.max(180, Math.min(320, Math.ceil(widest.labelW + widest.keysW + menu.checkW + Theme.gap + Theme.pad + 2 * padding + 16)))
    // the height comes from the entries, not from the rows (they are built only while open: a height taken from them
    // grew after the menu showed, and the menu moved under the pointer)
    height: rowsHeight + 2 * padding
    readonly property real rowsHeight: {
        let h = 0
        for (let i = 0; i < entries.length; i++) {
            const e = entries[i]
            h += Theme.popupRow + (i > 0 && entries[i - 1].group !== e.group ? dividerHeight : 0) + (e.heading ? headingHeight : 0)
        }
        return h
    }
    background: MenuBackground { }        // the one menu look: edge + soft shadow
    enter: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.fast } }
    exit: Transition { NumberAnimation { property: "opacity"; from: 1; to: 0; duration: Theme.fast } }

    property var at: null                    // where openAt asked for
    function openAt(px, py, flippedX) {
        at = { px: px, py: py, fx: flippedX }
        place()
        open()
    }
    function place() {
        if (!at) return
        const ov = parent, py = at.py
        // a side menu goes by its owner menu as it is NOW (the owner is sized and placed before it shows and stays put,
        // so the side menu never lands on the owner's own rows)
        const px = owner ? owner.x + owner.width : at.px, flippedX = owner ? owner.x : at.fx
        let x0 = px, y0 = py
        if (x0 + width > ov.width - Theme.grid) x0 = (flippedX !== undefined ? flippedX : px) - width
        if (y0 + height > ov.height - Theme.grid)
            y0 = (flippedX === undefined && py - height > Theme.grid) ? py - height : ov.height - height - Theme.grid
        x = Math.max(Theme.grid, Math.min(x0, ov.width - width - Theme.grid))     // asked from a point off the window:
        y = Math.max(Theme.grid, Math.min(y0, ov.height - height - Theme.grid))   // still whole on screen
    }
    // the window resized: still on screen (the one reason a visible menu moves)
    Connections { target: menu.parent; function onHeightChanged() { if (menu.visible) menu.place() } function onWidthChanged() { if (menu.visible) menu.place() } }
    function hasSub(i) { return !!(entries[i] && entries[i].sub && entries[i].sub.length) }
    function pick(i) {
        const e = entries[i]
        if (!e) return
        if (hasSub(i)) { openSub(i); return }
        var top = menu; while (top.owner) top = top.owner
        top.chosen = e.value; closeAll()
    }
    // the choice runs once the top menu has closed (its fade done): closing gives the keyboard back to where it was, so a
    // choice that takes the keyboard (Rename's name box) would lose it to the menu's own close a moment later
    property var chosen: undefined
    function closeAll() { close(); if (owner) owner.closeAll() }
    function openSub(i) {
        highlighted = i
        subLoader.active = true
        const s = subLoader.item
        if (!s) return
        const r = rep.itemAt(i)
        const p = r.mapToItem(parent, r.width + padding, 0)
        const left = r.mapToItem(parent, -padding, 0).x
        s.entries = entries[i].sub; s.owner = menu
        s.openAt(p.x, p.y - padding, left)
    }
    onAboutToShow: { highlighted = Math.max(0, entries.findIndex(e => !!e.checked)); keptShut = -1 }
    // a side menu closed by Esc or Left stays shut while the pointer rests on its row (closing it re-enters the row:
    // it would open again at once, and Esc would never get past it); it opens again once the pointer comes back
    property int keptShut: -1
    onClosed: {
        rested(""); if (subLoader.item) subLoader.item.close()
        if (chosen !== undefined) { const v = chosen; chosen = undefined; picked(v) }
    }
    Connections {
        target: subLoader.item; ignoreUnknownSignals: true
        function onPicked(v) { menu.picked(v) }
        function onRested(v) { menu.rested(v) }
        function onClosed() { menu.keptShut = menu.highlighted; list.forceActiveFocus() }
    }
    Loader { id: subLoader; active: false; source: "ActionMenu.qml" }

    // measure the widest label and key, to size the menu
    // (FontMetrics.advanceWidth(text) reads without writing: a TextMetrics' text set inside a binding loops)
    FontMetrics { id: tm; font.pixelSize: Theme.body; font.family: uiFont }
    FontMetrics { id: tk; font.pixelSize: Theme.label; font.family: uiFont }
    QtObject {
        id: widest
        property real labelW: { let w = 0; for (const e of menu.entries) w = Math.max(w, tm.advanceWidth(e.label), e.heading ? tm.advanceWidth(e.heading) - menu.checkW : 0); return w }
        property real keysW: { let w = 0; for (const e of menu.entries) if (e.keys) w = Math.max(w, tk.advanceWidth(e.keys) + Theme.gap); return w }
    }

    contentItem: Column {
        id: list
        focus: true
        spacing: 0
        Keys.onUpPressed: menu.highlighted = Math.max(0, menu.highlighted - 1)
        Keys.onDownPressed: menu.highlighted = Math.min(menu.entries.length - 1, menu.highlighted + 1)
        Keys.onReturnPressed: menu.pick(menu.highlighted)
        Keys.onEnterPressed: menu.pick(menu.highlighted)
        Keys.onRightPressed: if (menu.hasSub(menu.highlighted)) menu.openSub(menu.highlighted)
        Keys.onLeftPressed: if (menu.owner) menu.close()
        Repeater {      // rows only while open: a closed menu (every button's ▾, every ⋯) costs nothing when its entries change
            id: rep
            model: menu.visible ? menu.entries : []
            delegate: Item {
                id: row
                required property int index
                required property var modelData
                readonly property bool divided: index > 0 && menu.entries[index - 1].group !== modelData.group
                readonly property bool sub: !!(modelData.sub && modelData.sub.length)
                readonly property int lead: (divided ? menu.dividerHeight : 0) + (modelData.heading ? menu.headingHeight : 0)
                width: menu.availableWidth; height: Theme.popupRow + lead
                Rectangle {
                    visible: row.divided; x: Theme.gap - menu.padding; width: parent.width - 2 * (Theme.gap - menu.padding)
                    y: menu.dividerHeight / 2; height: 1; color: Theme.border
                }
                Text {
                    visible: !!row.modelData.heading
                    x: Theme.gap - menu.padding; y: row.lead - menu.headingHeight; height: menu.headingHeight
                    verticalAlignment: Text.AlignVCenter
                    text: row.modelData.heading || ""; color: Theme.fg2; font.pixelSize: Theme.label; font.family: uiFont
                    font.weight: Font.DemiBold
                }
                Rectangle {
                    objectName: "menu:" + row.modelData.value       // a walk clicks an entry by its value (clickobj)
                    y: row.lead; width: parent.width; height: Theme.popupRow; radius: 4
                    color: row.index === menu.highlighted ? Theme.hover : "transparent"
                    Text {
                        visible: menu.checks && !!row.modelData.checked
                        x: Theme.gap - menu.padding; anchors.verticalCenter: parent.verticalCenter
                        text: "✓"; color: Theme.fg; font.pixelSize: Theme.body; font.family: uiFont
                    }
                    Text {
                        id: lab
                        anchors { left: parent.left; leftMargin: Theme.gap - menu.padding + menu.checkW; verticalCenter: parent.verticalCenter }
                        width: parent.width - 2 * (Theme.gap - menu.padding) - menu.checkW - (chip.visible ? chip.width + Theme.gap : 0) - (row.sub ? 14 : 0)
                        text: row.modelData.label; elide: Text.ElideRight
                        color: Theme.fg; font.pixelSize: Theme.body; font.family: uiFont
                    }
                    Text {
                        id: chip
                        visible: !row.sub && !!row.modelData.keys
                        anchors { right: parent.right; rightMargin: Theme.gap - menu.padding; verticalCenter: parent.verticalCenter }
                        text: row.modelData.keys || ""; color: Theme.fg2; font.pixelSize: Theme.label; font.family: uiFont
                    }
                    Chevron {
                        visible: row.sub; rotation: -90; color: Theme.fg2
                        anchors { right: parent.right; rightMargin: Theme.gap - menu.padding; verticalCenter: parent.verticalCenter }
                    }
                    MouseArea {
                        id: ma
                        anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onEntered: {
                            menu.highlighted = row.index
                            if (!row.sub) menu.rested(row.modelData.value)
                            if (row.sub) { if (menu.keptShut !== row.index) menu.openSub(row.index) }
                            else if (subLoader.item) subLoader.item.close()
                        }
                        onExited: if (menu.keptShut === row.index) menu.keptShut = -1
                        onClicked: menu.pick(row.index)
                    }
                    HoverTip { text: lab.truncated ? row.modelData.label : ""; hovered: ma.containsMouse }
                }
            }
        }
    }
}
