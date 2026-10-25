import QtQuick
import QtQuick.Controls as QQC
import RostrumKit

// The insert chain of a track, bus or the master: one line per effect, top to bottom in insert order (it scrolls when
// there are many), then "+ Effect" pinned under the lines so it is always there, on every strip.
// A chip selects its effect (the inspector edits it); dragging a line up or down moves it in the chain (effect.move, one
// change when you let go). "+ Effect" lists the effect types; picking one is effect.add.
Item {
    id: chain
    property var chips: []
    property string ownerId: ""
    readonly property real contentHeight: list.contentHeight + (chips.length ? 2 : 0) + plus.height     // all the lines and "+ Effect"
    readonly property real rowStep: 24                   // a line (22) and the gap between lines (2)

    Flickable {
        id: list
        anchors { left: parent.left; right: parent.right; top: parent.top }
        height: Math.max(0, chain.height - plus.height - 2)
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
                        property real startY: 0
                        property real shift: 0
                        property bool moved: false
                        readonly property int target: Math.max(0, Math.min(chain.chips.length - 1, slot.index + Math.round(shift / chain.rowStep)))
                        preventStealing: moved
                        onPressed: (m) => { startY = m.y; shift = 0; moved = false }
                        onPositionChanged: (m) => {
                            if (!pressed) return
                            if (!moved && Math.abs(m.y - startY) > 4) { moved = true; list.dragging = true }
                            if (moved) shift = Math.max(-slot.index * chain.rowStep, Math.min((chain.chips.length - 1 - slot.index) * chain.rowStep, m.y - startY))
                        }
                        onReleased: {
                            const was = moved, to = target
                            moved = false; shift = 0; list.dragging = false
                            if (!was) backend.select(slot.modelData.id)
                            else if (to !== slot.index) mixer.moveEffect(slot.modelData.id, to)
                        }
                        onCanceled: { moved = false; shift = 0; list.dragging = false }
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
        anchors.bottom: parent.bottom
        tip: menu.opened ? "" : chain.ownerId === "master" ? "Add an effect to the master" : "Add an effect to this track"
        onClicked: { menu.showPlugins = false; mixer.plugins.scan(); menu.open() }
    }
    SmallPopup {
        id: menu
        property bool showPlugins: false      // the second page of the menu: the scanned plug-ins
        parent: plus
        // below "+ Effect" when it fits in the window, else above it (the Mixer sits at the bottom), never off the window
        y: { const top = plus.mapToItem(null, 0, 0).y, room = chain.Window.height - 8
             return top + plus.height + 2 + implicitHeight <= room ? plus.height + 2 : Math.max(8 - top, -implicitHeight - 2) }
        width: showPlugins ? 220 : 132; padding: Theme.grid
        background: Rectangle { color: Theme.raised; radius: Theme.radiusCtl; border.color: Theme.popupEdge }
        contentItem: Column {
            Repeater {
                model: menu.showPlugins ? [] : mixer.effectTypes
                delegate: Rectangle {
                    required property var modelData
                    width: 124; height: Theme.popupRow; radius: 4
                    color: pick.containsMouse ? Theme.hover : "transparent"
                    Text { anchors.left: parent.left; anchors.leftMargin: Theme.gap - 2; anchors.verticalCenter: parent.verticalCenter
                           text: modelData.label; color: Theme.fg; font.pixelSize: Theme.body; font.family: uiFont }
                    MouseArea { id: pick; anchors.fill: parent; hoverEnabled: true
                                onClicked: { menu.close(); mixer.addEffect(chain.ownerId, modelData.value) } }
                }
            }
            Rectangle {
                visible: !menu.showPlugins
                width: 124; height: Theme.popupRow; radius: 4
                color: plugRow.containsMouse ? Theme.hover : "transparent"
                Text { anchors.left: parent.left; anchors.leftMargin: Theme.gap - 2; anchors.verticalCenter: parent.verticalCenter
                       text: "Add plug-in…"; color: Theme.fg2; font.pixelSize: Theme.body; font.family: uiFont }
                MouseArea { id: plugRow; anchors.fill: parent; hoverEnabled: true; onClicked: menu.showPlugins = true }
            }
            PluginList {
                visible: menu.showPlugins; width: menu.width - 2 * Theme.grid
                choices: mixer.plugins.effects
                onPicked: (key) => { menu.close(); mixer.plugins.addEffect(chain.ownerId, key) }
            }
        }
    }
}
