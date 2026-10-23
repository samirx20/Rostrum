import QtQuick
import QtQuick.Controls as QQC
import RostrumKit
import "MixFormat.js" as F

// The insert chain of a track, bus or the master: one line per effect, top to bottom in insert order, then "+ Effect"
// (always there, on every strip).
// A chip selects its effect (the inspector edits it). "+ Effect" lists the effect types; picking one is effect.add.
Flickable {
    id: chain
    property var chips: []
    property string ownerId: ""
    contentHeight: flow.height; clip: true; boundsBehavior: Flickable.StopAtBounds

    Column {
        id: flow
        width: chain.width
        spacing: 2
        Repeater {
            model: chain.chips
            delegate: MixChip {
                required property var modelData
                text: modelData.label; dim: modelData.bypass; row: true; width: chain.width; maxWidth: chain.width
                selected: backend.selected === modelData.id
                onClicked: backend.select(modelData.id)
            }
        }
        MixChip { id: plus; text: "+ Effect"; row: true; flat: true; width: chain.width; tip: menu.opened ? "" : chain.ownerId === "master" ? "Add an effect to the master" : "Add an effect to this track"; onClicked: { menu.showPlugins = false; mixer.plugins.scan(); menu.open() } }
    }
    QQC.Popup {
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
                    required property string modelData
                    width: 124; height: Theme.popupRow; radius: 4
                    color: pick.containsMouse ? Theme.hover : "transparent"
                    Text { anchors.left: parent.left; anchors.leftMargin: Theme.gap - 2; anchors.verticalCenter: parent.verticalCenter
                           text: F.effectName(modelData); color: Theme.fg; font.pixelSize: Theme.body; font.family: uiFont }
                    MouseArea { id: pick; anchors.fill: parent; hoverEnabled: true
                                onClicked: { menu.close(); mixer.addEffect(chain.ownerId, modelData) } }
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
