import QtQuick
import QtQuick.Controls as QQC
import RostrumKit

// A rail group's flyout (design v2 §2.1, mockup 02): beside the rail at the group's icon, its entries as icon + name,
// the key in the corner; no descriptions. A click picks one and closes it; Esc or a click anywhere else closes it.
QQC.Popup {
    id: fly
    property string group: ""
    property var items: []
    signal picked(var entry)
    parent: QQC.Overlay.overlay
    padding: 6
    closePolicy: QQC.Popup.CloseOnPressOutside | QQC.Popup.CloseOnEscape
    background: Rectangle { color: Theme.raised; radius: Theme.radiusPanel; border.color: Theme.popupEdge }
    function show(g, button) {
        group = g.id; items = g.items
        const p = button.mapToItem(parent, button.width, 0)
        x = p.x + 8
        y = Math.max(8, Math.min(p.y - padding, parent.height - implicitHeight - 8))
        open()
    }
    onClosed: group = ""
    contentItem: Grid {
        columns: Math.min(3, fly.items.length)
        spacing: 2
        Repeater {
            model: fly.items
            delegate: Rectangle {
                id: cell
                required property var modelData
                readonly property bool on: modelData.tool !== undefined && modelData.tool === backend.tool
                objectName: "fly_" + (modelData.tool || modelData.act)
                width: 84; height: 58; radius: Theme.radiusCtl
                color: tap.pressed || cell.on ? Theme.active : hover.hovered ? Theme.hover : "transparent"
                ToolIcon { anchors { horizontalCenter: parent.horizontalCenter; top: parent.top; topMargin: 9 }
                           name: cell.modelData.icon; ink: cell.on || hover.hovered ? Theme.fg : Theme.fg2 }
                Text {
                    anchors { horizontalCenter: parent.horizontalCenter; bottom: parent.bottom; bottomMargin: 7 }
                    width: parent.width - 6; horizontalAlignment: Text.AlignHCenter; elide: Text.ElideRight
                    text: cell.modelData.name; color: cell.on || hover.hovered ? Theme.fg : Theme.fg2
                    font.family: uiFont; font.pixelSize: Theme.label
                }
                Text {     // its key, small, in the corner
                    anchors { right: parent.right; top: parent.top; margins: 4 }
                    text: cell.modelData.job && Window.window && Window.window.keyFor ? Window.window.keyFor(cell.modelData.job) : ""
                    color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label - 2
                }
                HoverHandler { id: hover; cursorShape: Qt.PointingHandCursor }
                MouseArea { id: tap; anchors.fill: parent; onClicked: fly.picked(cell.modelData) }
            }
        }
    }
}
