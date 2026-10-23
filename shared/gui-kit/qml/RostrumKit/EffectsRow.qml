import QtQuick
import "."

// The settings panel's "Effects (n) +" section: the row, then each added effect as a folded group (a chevron and its
// name, × to remove it, its own settings under it). `part` is bridge.effects (rostrum_gui/effects.py: add, remove,
// what + may add now). Absent (zero height) when the selection takes no effects. Nothing here edits beside an
// operation: + calls part.add(type), × calls the group's remove(), the settings are InspectorRows on the group.
Item {
    id: fx
    property var part: null
    readonly property bool on: !!fx.part && fx.part.shown
    width: parent ? parent.width : 0
    height: on ? col.height : 0
    visible: on

    Column {
        id: col
        width: parent.width
        Item {  // the row: "Effects (2)" and the +, ending on the fields' right edge like the other headers
            width: Theme.wideFor(parent.width); height: Theme.row + Theme.groupGap / 2
            Text { anchors.left: parent.left; anchors.bottom: parent.bottom; anchors.bottomMargin: Theme.grid + 2
                   text: "Effects" + (fx.on && fx.part.count ? " (" + fx.part.count + ")" : ""); color: Theme.fg2
                   font.family: uiFont; font.pixelSize: Theme.body; font.weight: Font.DemiBold }
            IconButton {
                id: plus
                objectName: "addEffect"
                anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; anchors.verticalCenterOffset: Theme.grid
                implicitWidth: Theme.field; implicitHeight: Theme.field; kind: "ghost"; glyph: "+"
                tip: "Add an effect"; help: "Add an effect to this layer; its settings appear under Effects."
                onClicked: { choices.entries = fx.part.addable(); const p = plus.mapToItem(null, plus.width, plus.height + 2)
                             choices.openAt(p.x, p.y, p.x) }
            }
            ActionMenu { id: choices; onPicked: (v) => fx.part.add(v) }
        }
        Repeater {     // a search for an effect the layer doesn't have yet ("blur"): one line to add it
            model: fx.on ? fx.part.found : []
            delegate: Item {
                id: hit
                required property var modelData
                width: col.width; height: Theme.row
                Rectangle { anchors.fill: parent; radius: Theme.radiusCtl; color: Theme.hover; visible: hitArea.containsMouse }
                Text { anchors.left: parent.left; anchors.leftMargin: Theme.grid; anchors.verticalCenter: parent.verticalCenter
                       text: "Add " + hit.modelData.label; color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body }
                MouseArea { id: hitArea; objectName: "addFound:" + hit.modelData.value; anchors.fill: parent; hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor; onClicked: fx.part.add(hit.modelData.value) }
            }
        }
        Repeater {
            model: fx.on ? fx.part.groups : []
            delegate: Column {
                id: grp
                required property var modelData
                readonly property var g: modelData
                width: col.width
                Item {  // the group's header
                    width: parent.width; height: Theme.row
                    Chevron { id: chev; anchors.left: parent.left; anchors.verticalCenter: parent.verticalCenter
                              rotation: grp.g.open ? 0 : -90; color: head.containsMouse ? Theme.fg : Theme.fg3
                              Behavior on rotation { NumberAnimation { duration: Theme.fast; easing.type: Theme.revealEasing } } }
                    NameLabel { anchors.left: chev.right; anchors.leftMargin: Theme.grid + 2; anchors.right: gone.left
                                anchors.verticalCenter: parent.verticalCenter; text: grp.g.label
                                color: head.containsMouse ? Theme.fg : Theme.fg2; font.pixelSize: Theme.body; font.weight: Font.DemiBold }
                    MouseArea { id: head; anchors.left: parent.left; anchors.right: gone.left; height: parent.height
                                hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: grp.g.toggle() }
                    IconButton { id: gone; objectName: "removeEffect"; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                                 implicitWidth: Theme.field; implicitHeight: Theme.field; kind: "ghost"; glyph: "×"
                                 tip: "Remove"; help: "Remove this effect from the layer."; onClicked: grp.g.remove() }
                }
                Item {  // its settings, open or folded (height eases)
                    width: parent.width; clip: true
                    height: grp.g.open ? inner.height : 0
                    visible: height > 0
                    Behavior on height { NumberAnimation { duration: Theme.reveal; easing.type: Theme.revealEasing } }
                    Column {
                        id: inner
                        width: parent.width
                        Repeater { model: grp.g.rows; delegate: InspectorRow { bridge: grp.g } }
                    }
                }
            }
        }
    }
}
