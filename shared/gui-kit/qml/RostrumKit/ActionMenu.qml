import QtQuick
import QtQuick.Controls as QQC
import "."

// The menu of actions (right-click, a button's ▾, the context bar's ⋯). `entries`: [{value, label, keys, group, sub}].
//  - `keys` shows as a muted chip at the right; a thin divider sits wherever `group` changes;
//  - an entry with `sub` (a list of entries) opens a side menu on hover or Right; Left or Esc closes it;
//  - openAt(x, y [, xIfFlipped]) opens at a point in window coordinates and stays on screen (flips left / up);
//  - Up / Down move, Enter picks, Esc closes. Choosing sends picked(value) from the top menu, whatever its depth.
//  - when any entry has `checked`, a fixed left column shows ✓ on the checked ones (the chosen entry);
// Long labels shorten with "…" and show whole on hover. Width fits the longest label + key (180 to 320).
QQC.Popup {
    id: menu
    property var entries: []
    property int highlighted: 0
    property var owner: null                 // the menu this one is a side menu of
    readonly property int dividerHeight: 9
    readonly property bool checks: entries.some(e => e.checked !== undefined)   // reserve the ✓ column
    readonly property int checkW: checks ? 18 : 0
    signal picked(string value)

    parent: QQC.Overlay.overlay
    padding: Theme.grid
    focus: true
    closePolicy: QQC.Popup.CloseOnEscape | QQC.Popup.CloseOnPressOutside
    width: Math.max(180, Math.min(320, Math.ceil(widest.labelW + widest.keysW + menu.checkW + Theme.gap + Theme.pad + 2 * padding + 16)))
    height: list.implicitHeight + 2 * padding
    background: Rectangle { color: Theme.raised; radius: Theme.radiusCtl; border.color: Theme.popupEdge }
    enter: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.fast } }
    exit: Transition { NumberAnimation { property: "opacity"; from: 1; to: 0; duration: Theme.fast } }

    property var at: null                    // where openAt asked for: placed again when the size settles
    function openAt(px, py, flippedX) {
        at = { px: px, py: py, fx: flippedX }
        place()
        open()
    }
    function place() {
        if (!at) return
        const ov = parent, px = at.px, py = at.py, flippedX = at.fx
        let x0 = px, y0 = py
        if (x0 + width > ov.width - Theme.grid) x0 = (flippedX !== undefined ? flippedX : px) - width
        if (y0 + height > ov.height - Theme.grid)
            y0 = (flippedX === undefined && py - height > Theme.grid) ? py - height : ov.height - height - Theme.grid
        x = Math.max(Theme.grid, x0); y = Math.max(Theme.grid, y0)
    }
    onHeightChanged: place()                 // the entries were set just before openAt: their size comes a moment later
    onWidthChanged: place()
    function hasSub(i) { return !!(entries[i] && entries[i].sub && entries[i].sub.length) }
    function pick(i) {
        const e = entries[i]
        if (!e) return
        if (hasSub(i)) { openSub(i); return }
        closeAll(); picked(e.value)
    }
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
    onAboutToShow: highlighted = 0
    onClosed: if (subLoader.item) subLoader.item.close()
    Connections {
        target: subLoader.item; ignoreUnknownSignals: true
        function onPicked(v) { menu.picked(v) }
        function onClosed() { list.forceActiveFocus() }
    }
    Loader { id: subLoader; active: false; source: "ActionMenu.qml" }

    // measure the widest label and key, to size the menu
    // (FontMetrics.advanceWidth(text) reads without writing: a TextMetrics' text set inside a binding loops)
    FontMetrics { id: tm; font.pixelSize: Theme.body; font.family: uiFont }
    FontMetrics { id: tk; font.pixelSize: Theme.label; font.family: uiFont }
    QtObject {
        id: widest
        property real labelW: { let w = 0; for (const e of menu.entries) w = Math.max(w, tm.advanceWidth(e.label)); return w }
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
        Repeater {
            id: rep
            model: menu.entries
            delegate: Item {
                id: row
                required property int index
                required property var modelData
                readonly property bool divided: index > 0 && menu.entries[index - 1].group !== modelData.group
                readonly property bool sub: !!(modelData.sub && modelData.sub.length)
                width: menu.availableWidth; height: Theme.popupRow + (divided ? menu.dividerHeight : 0)
                Rectangle {
                    visible: row.divided; x: Theme.gap - menu.padding; width: parent.width - 2 * (Theme.gap - menu.padding)
                    y: menu.dividerHeight / 2; height: 1; color: Theme.border
                }
                Rectangle {
                    y: row.divided ? menu.dividerHeight : 0; width: parent.width; height: Theme.popupRow; radius: 4
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
                        text: row.modelData.keys || ""; color: Theme.fg3; font.pixelSize: Theme.label; font.family: uiFont
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
                            if (row.sub) menu.openSub(row.index)
                            else if (subLoader.item) subLoader.item.close()
                        }
                        onClicked: menu.pick(row.index)
                    }
                    HoverTip { text: lab.truncated ? row.modelData.label : ""; hovered: ma.containsMouse }
                }
            }
        }
    }
}
