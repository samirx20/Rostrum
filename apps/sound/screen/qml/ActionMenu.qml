import QtQuick
import QtQuick.Controls as QQC
import RostrumKit

// A menu of actions on the selection (screensound/actions.py; the same file as Rostrum2D's qml/ActionMenu.qml, to become one kit copy): `entries` is [{value, label, hint (the shortcut), group}];
// a thin line separates each group from the one before. Choosing one closes the menu and sends picked(value).
// Up / Down move, Enter picks, Esc closes. Only what applies is ever listed, so nothing is greyed.
QQC.Popup {
    id: menu
    property var entries: []
    property int highlighted: 0
    signal picked(string value)
    width: 236
    padding: Theme.grid
    focus: true
    closePolicy: QQC.Popup.CloseOnEscape | QQC.Popup.CloseOnPressOutside
    onAboutToShow: highlighted = 0
    // Open at (px, py) of the item it sits in, moved up as far as it needs to stay inside the window.
    function openAt(px, py) {
        const dividers = entries.filter((e, i) => i > 0 && entries[i - 1].group !== e.group).length
        const h = entries.length * Theme.popupRow + dividers * Theme.grid + padding * 2
        const g = parent.mapToItem(null, 0, py), room = parent.Window.height - h - Theme.gap
        x = Math.max(Theme.grid, Math.min(px, parent.Window.width - width - Theme.grid))
        y = py - Math.max(0, g.y - room)
        if (entries.length) open()
    }
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
            delegate: Item {
                id: row
                required property int index
                required property var modelData
                readonly property bool divided: index > 0 && menu.entries[index - 1].group !== modelData.group
                width: menu.availableWidth; height: Theme.popupRow + (divided ? Theme.grid : 0)
                Rectangle { visible: row.divided; width: parent.width; height: 1; y: Theme.grid / 2 - 1; color: Theme.popupEdge }
                Rectangle {
                    y: row.divided ? Theme.grid : 0; width: parent.width; height: Theme.popupRow; radius: 4
                    color: row.index === menu.highlighted ? Theme.hover : "transparent"
                    Text {
                        anchors { left: parent.left; leftMargin: Theme.gap - menu.padding; right: hint.left; rightMargin: Theme.gap; verticalCenter: parent.verticalCenter }
                        text: row.modelData.label; elide: Text.ElideRight
                        color: Theme.fg; font.pixelSize: Theme.body; font.family: uiFont
                    }
                    KeyHint { id: hint; visible: row.modelData.hint !== ""; text: row.modelData.hint
                              anchors.right: parent.right; anchors.rightMargin: Theme.grid; anchors.verticalCenter: parent.verticalCenter }
                    MouseArea { anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                onEntered: menu.highlighted = row.index; onClicked: row.parent.parent.pick(row.index) }
                }
            }
        }
    }
}
