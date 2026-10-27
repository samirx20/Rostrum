import QtQuick
import QtQuick.Controls as QQC
import RostrumKit

// The insert chain of a track, bus or the master: one line per effect, top to bottom in insert order (it scrolls when
// there are many), then "+ Effect" pinned under the lines so it is always there, on every strip.
// A chip selects its effect (the inspector edits it); dragging a line up or down moves it in the chain (effect.move, one
// change when you let go; the kit's chip by the pointer says the place it lands, "Place 2 of 4"; Esc puts it back).
// "+ Effect" lists the effect types; picking one is effect.add. Right-click a line: its own
// menu, Remove (as the Delete key on the selected effect).
Item {
    id: chain
    property var chips: []
    property string ownerId: ""
    readonly property real contentHeight: list.contentHeight + (chips.length ? 2 : 0) + plus.height     // all the lines and "+ Effect"
    readonly property real rowStep: 24                   // a line (22) and the gap between lines (2)

    Flickable {
        id: list
        anchors { left: parent.left; right: parent.right; top: parent.top }
        height: Math.min(flow.height, Math.max(0, chain.height - plus.height - 2))   // the room the strip keeps (MixStrip) may be more
        contentHeight: flow.height; clip: true; boundsBehavior: Flickable.StopAtBounds
        interactive: !dragging
        property bool dragging: false
        Column {
            id: flow
            width: list.width
            spacing: 2
            Repeater {
                model: chain.chips
                delegate: Item {
                    id: slot
                    required property var modelData
                    required property int index
                    width: list.width; height: 22
                    z: grab.pressed && grab.moved ? 2 : 0
                    MixChip {
                        id: chip
                        objectName: "effect:" + slot.modelData.id
                        text: slot.modelData.label; dim: slot.modelData.bypass; row: true; width: parent.width; maxWidth: parent.width
                        selected: backend.selected === slot.modelData.id
                        y: grab.pressed && grab.moved ? grab.shift : 0
                        opacity: grab.pressed && grab.moved ? 0.85 : dim ? 0.45 : 1
                        onClicked: {}     // the grab area below selects (a click) or moves (a drag)
                    }
                    MouseArea {
                        id: grab
                        anchors.fill: parent
                        acceptedButtons: Qt.LeftButton | Qt.RightButton
                        property real startY: 0
                        property real shift: 0
                        property bool moved: false
                        readonly property int target: Math.max(0, Math.min(chain.chips.length - 1, slot.index + Math.round(shift / chain.rowStep)))
                        preventStealing: moved
                        onPressed: (m) => { startY = m.y; shift = 0; moved = false
                                            if (m.button === Qt.RightButton) { backend.select(slot.modelData.id); chain.menuFor(slot.modelData.id, grab, m.x, m.y) } }
                        property bool gone: false          // Esc'd: the release does nothing
                        onPositionChanged: (m) => {
                            if (!pressed || !(pressedButtons & Qt.LeftButton) || gone) return
                            if (!moved && Math.abs(m.y - startY) > 4) { moved = true; list.dragging = true; dragEsc.holdEsc() }
                            if (moved) shift = Math.max(-slot.index * chain.rowStep, Math.min((chain.chips.length - 1 - slot.index) * chain.rowStep, m.y - startY))
                        }
                        onReleased: (m) => {
                            if (m.button === Qt.RightButton) return
                            const was = moved, to = target
                            if (moved) dragEsc.letEsc()
                            moved = false; shift = 0; list.dragging = false
                            if (gone) { gone = false; return }
                            if (!was) backend.select(slot.modelData.id)
                            else if (to !== slot.index) mixer.moveEffect(slot.modelData.id, to)
                        }
                        onCanceled: { if (moved) dragEsc.letEsc(); moved = false; shift = 0; list.dragging = false; gone = false }
                        Connections {   // Esc while a line is dragged: it goes back to its place
                            target: dragEsc
                            function onCancelled() { if (grab.moved) { grab.moved = false; grab.shift = 0; list.dragging = false; grab.gone = true } }
                        }
                    }
                    DragLabel {   // the place it lands
                        parent: chain; z: 1000
                        at: grab.mapToItem(chain, grab.mouseX, grab.mouseY)
                        text: grab.pressed && grab.moved ? "Place " + (grab.target + 1) + " of " + chain.chips.length : ""
                    }
                    Rectangle {   // where it will land: a line over the gap above / under the lines it passes
                        objectName: "effect-drop"
                        visible: grab.pressed && grab.moved && grab.target !== slot.index
                        x: 0; width: parent.width; height: 2; radius: 1; color: Theme.accent
                        y: grab.target < slot.index ? (grab.target - slot.index) * chain.rowStep - 2 : (grab.target - slot.index) * chain.rowStep + 22
                    }
                }
            }
        }
    }
    MixChip {
        id: plus
        objectName: "addEffect"
        text: "+ Effect"; row: true; flat: true; width: chain.width
        y: list.height + (chain.chips.length ? 2 : 0)      // right under the lines
        tip: menu.item && menu.item.opened ? "" : chain.ownerId === "master" ? "Add an effect to the master" : "Add an effect to this track"
        onClicked: { menu.active = true; menu.item.showPlugins = false; mixer.plugins.scan(); menu.item.open() }
    }
    function menuFor(id, item, x, y) {   // an effect's own menu, at the pointer
        own.active = true
        const p = item.mapToItem(null, x, y)
        own.item.target = id; own.item.openAt(p.x, p.y)
    }
    Loader {   // made on the first right-click (every strip has a chain)
        id: own
        active: false
        sourceComponent: ActionMenu {
            objectName: "effectMenu"
            property string target: ""
            entries: [{ value: "remove", label: "Remove", keys: "Delete", group: "", sub: [] }]
            onPicked: (v) => { if (v === "remove") mixer.remove(target) }
        }
    }
    Loader {   // the menu is made on the first click (every strip has a "+ Effect"; a closed menu made its rows anyway)
        id: menu
        active: false
        sourceComponent: effects
    }
    Component {
        id: effects
        SmallPopup {
            id: list
            property bool showPlugins: false      // the second page of the menu: the scanned plug-ins
            parent: plus
            // below "+ Effect" when it fits in the window, else above it (the Mixer sits at the bottom), never off the window
            y: { const top = plus.mapToItem(null, 0, 0).y, room = chain.Window.height - 8
                 return top + plus.height + 2 + implicitHeight <= room ? plus.height + 2 : Math.max(8 - top, -implicitHeight - 2) }
            width: showPlugins ? 220 : 132; padding: Theme.grid
            background: Rectangle { color: Theme.raised; radius: Theme.radiusCtl; border.color: Theme.popupEdge }
            contentItem: Column {
                Repeater {
                    model: list.showPlugins ? [] : mixer.effectTypes
                    delegate: Rectangle {
                        required property var modelData
                        width: 124; height: Theme.popupRow; radius: 4
                        color: pick.containsMouse ? Theme.hover : "transparent"
                        Text { anchors.left: parent.left; anchors.leftMargin: Theme.gap - 2; anchors.verticalCenter: parent.verticalCenter
                               text: modelData.label; color: Theme.fg; font.pixelSize: Theme.body; font.family: uiFont }
                        MouseArea { id: pick; anchors.fill: parent; hoverEnabled: true
                                    onClicked: { list.close(); mixer.addEffect(chain.ownerId, modelData.value) } }
                    }
                }
                Rectangle {
                    visible: !list.showPlugins
                    width: 124; height: Theme.popupRow; radius: 4
                    color: plugRow.containsMouse ? Theme.hover : "transparent"
                    Text { anchors.left: parent.left; anchors.leftMargin: Theme.gap - 2; anchors.verticalCenter: parent.verticalCenter
                           text: "Add plug-in…"; color: Theme.fg2; font.pixelSize: Theme.body; font.family: uiFont }
                    MouseArea { id: plugRow; anchors.fill: parent; hoverEnabled: true; onClicked: list.showPlugins = true }
                }
                PluginList {
                    visible: list.showPlugins; width: list.width - 2 * Theme.grid
                    choices: mixer.plugins.effects
                    onPicked: (key) => { list.close(); mixer.plugins.addEffect(chain.ownerId, key) }
                }
            }
        }
    }
}
