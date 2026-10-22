import QtQuick
import RostrumKit

// The context bar (INTERACTION.md §1.2): one row at the top centre of the area it sits in (the arrangement, the
// Editor), never wrapping: a count chip ("5 notes"), the primary actions in rank order (backend.actionBar: up to
// five; the lowest fold into ⋯ one by one when the area is narrow), then ⋯ for the rest (backend.overflowMenu).
// Never the edit block (Copy, Cut, Paste, Duplicate, Rename, Delete: keys and the right-click menu). Hidden while
// dragging, while playing and while a right-click menu is open (`busy`). Only in the focused area (`active`).
// A Sound-side stand-in for the kit's ContextBar (INTERACTION.md Part 5, piece 2): the same data, thin QML.
Item {
    id: bar
    property bool active: true
    property bool busy: false
    readonly property int most: 5
    property var items: []
    function refresh() { items = backend.actionBar() }
    Component.onCompleted: refresh()
    Connections {
        target: backend
        function onPicksChanged() { bar.refresh() }
        function onRangeChanged() { bar.refresh() }
        function onTimeChanged() { if (backend.selectedIds.length) bar.refresh() }   // Split at playhead comes and goes
        function onDocChanged() { bar.refresh() }
    }
    readonly property bool showing: active && !busy && !backend.playing && items.length > 0
    readonly property bool menuOpen: choices.opened
    width: parent ? parent.width : 0
    height: Theme.button

    // how many buttons fit: the widest run of the first n (n ≤ most) with the chip and ⋯ inside the area
    readonly property int shown: {
        var room = width - 2 * Theme.pad - chip.width - more.width - 2 * Theme.grid, used = 0, n = 0
        for (var i = 0; i < Math.min(most, measure.count); i++) {
            var it = measure.itemAt(i)
            if (!it || used + it.width > room) break
            used += it.width; n++
        }
        return n
    }

    ActionMenu { id: choices; parent: bar; onPicked: (key) => key.startsWith("menu:") ? bar.openMenu(backend.subMenu(key), choices.x, choices.y) : backend.runAction(key) }
    function openMenu(entries, px, py) { choices.entries = entries; choices.openAt(px, py) }

    Row {   // measuring only: the buttons' natural widths
        visible: false
        Repeater { id: measure; model: bar.items; delegate: BarButton { required property var modelData; label: modelData.label + (modelData.menu.length ? " ▾" : "") } }
    }
    Rectangle {
        id: strip
        visible: bar.showing
        z: 3
        anchors.horizontalCenter: parent.horizontalCenter
        height: Theme.button; width: row.width + Theme.grid * 2
        radius: Theme.radiusCtl; color: Theme.raised; border.color: Theme.popupEdge
        Row {
            id: row
            x: Theme.grid; height: parent.height
            Text {   // the count chip: what the actions act on
                id: chip
                anchors.verticalCenter: parent.verticalCenter
                leftPadding: Theme.grid; rightPadding: Theme.gap
                text: backend.selectionWords !== "" ? backend.selectionWords : "Time range"
                color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label; font.features: { "tnum": 1 }
            }
            Repeater {
                model: bar.items.slice(0, bar.shown)
                delegate: BarButton {
                    required property var modelData
                    label: modelData.label + (modelData.menu.length ? " ▾" : "")
                    tip: modelData.shortcut
                    onClicked: modelData.menu.length ? bar.openMenu(modelData.menu, strip.x + x, strip.y + strip.height + 2) : backend.runAction(modelData.key)
                }
            }
            BarButton {
                id: more
                visible: backend.overflowMenu(bar.shown).length > 0 || bar.items.length > bar.shown
                label: "⋯"; tip: "More actions"
                onClicked: bar.openMenu(backend.overflowMenu(bar.shown), strip.x + x, strip.y + strip.height + 2)
            }
        }
    }

    component BarButton: Rectangle {
        id: button
        property string label
        property string tip
        signal clicked
        height: Theme.button - Theme.grid; width: text.implicitWidth + Theme.gap * 2; y: Theme.grid / 2
        radius: 4; color: area.containsMouse ? Theme.hover : "transparent"
        Text { id: text; anchors.centerIn: parent; text: button.label; color: Theme.fg
               font.family: uiFont; font.pixelSize: Theme.body }
        MouseArea { id: area; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: button.clicked() }
        HoverTip { text: button.tip; hovered: area.containsMouse && button.tip !== ""; pressed: area.pressed }
    }
}
