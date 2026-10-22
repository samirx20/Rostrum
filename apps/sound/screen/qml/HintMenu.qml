import QtQuick
import QtQuick.Controls as QQC
import RostrumKit

// The kit's Menu with a shortcut chip at the right of an entry: `entries` [{value, label, hint}], picked(value).
// (The kit's Menu has no hints yet; this goes when it has.) Up / Down move, Enter picks, Esc closes.
QQC.Popup {
    id: menu
    property var entries: []
    property int highlighted: 0
    signal picked(string value)
    y: parent ? parent.height + 2 : 0
    width: 260
    padding: Theme.grid
    focus: true
    onAboutToShow: highlighted = 0
    background: Rectangle { color: Theme.raised; radius: Theme.radiusCtl; border.color: Theme.popupEdge }
    enter: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.fast } }
    exit: Transition { NumberAnimation { property: "opacity"; from: 1; to: 0; duration: Theme.fast } }
    contentItem: Column {
        focus: true
        function pick(i) { const v = menu.entries[i].value; menu.close(); menu.picked(v) }
        Keys.onUpPressed: menu.highlighted = Math.max(0, menu.highlighted - 1)
        Keys.onDownPressed: menu.highlighted = Math.min(menu.entries.length - 1, menu.highlighted + 1)
        Keys.onReturnPressed: pick(menu.highlighted)
        Keys.onEnterPressed: pick(menu.highlighted)
        Repeater {
            model: menu.entries
            delegate: Rectangle {
                id: row
                required property int index
                required property var modelData
                width: menu.availableWidth; height: Theme.popupRow; radius: 4
                color: index === menu.highlighted ? Theme.hover : "transparent"
                Text {
                    anchors { left: parent.left; leftMargin: Theme.gap - menu.padding; right: chip.visible ? chip.left : parent.right
                              rightMargin: Theme.gap; verticalCenter: parent.verticalCenter }
                    text: row.modelData.label; elide: Text.ElideRight
                    color: Theme.fg; font.pixelSize: Theme.body; font.family: uiFont
                }
                KeyHint { id: chip; visible: !!row.modelData.hint; text: row.modelData.hint || ""
                          anchors { right: parent.right; rightMargin: Theme.grid; verticalCenter: parent.verticalCenter } }
                MouseArea { anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onEntered: menu.highlighted = row.index; onClicked: row.parent.pick(row.index) }
            }
        }
    }
}
