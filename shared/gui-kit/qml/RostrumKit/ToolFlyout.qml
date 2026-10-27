import QtQuick
import QtQuick.Controls as QQC
import "."

// A rail group's flyout (design v2 §2.1, mockup 02): beside the rail at the group's icon, its entries as icon + name;
// the key, where there is one, in the hover tip, with the entry's own `help` when it has one ("Soft light": the
// photographers' softbox). An entry's icon is RailIcon's. A click picks one and
// closes it; Esc or a click anywhere else closes it. ToolRail owns it.
SmallPopup {
    id: fly
    property string group: ""
    property var items: []
    property string current: ""        // the active tool: its entry reads as on
    property var kinds: ({})           // ToolRail.iconKinds
    signal picked(var entry)
    parent: QQC.Overlay.overlay
    padding: 6
    focus: true                        // Esc reaches it: the first Esc closes the panel (the app's next ones step back)
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
                readonly property bool on: modelData.tool !== undefined && modelData.tool === fly.current
                objectName: "fly_" + (modelData.tool || modelData.act)   // fly_star, fly_image, …
                width: 84; height: 58; radius: Theme.radiusCtl
                color: tap.pressed || cell.on ? Theme.active : hover.hovered ? Theme.hover : "transparent"
                RailIcon { anchors { horizontalCenter: parent.horizontalCenter; top: parent.top; topMargin: 9 }
                           entry: cell.modelData; kinds: fly.kinds; ink: cell.on || hover.hovered ? Theme.fg : Theme.fg2 }
                Text {
                    anchors { horizontalCenter: parent.horizontalCenter; bottom: parent.bottom; bottomMargin: 7 }
                    width: parent.width - 6; horizontalAlignment: Text.AlignHCenter; elide: Text.ElideRight
                    text: cell.modelData.name; color: cell.on || hover.hovered ? Theme.fg : Theme.fg2
                    font.family: uiFont; font.pixelSize: Theme.body
                }
                HoverHandler { id: hover; cursorShape: Qt.PointingHandCursor }
                HoverTip { hovered: hover.hovered; pressed: tap.pressed; text: cell.modelData.name; help: cell.modelData.help || ""     // its key, as every tile's
                           key: cell.modelData.job && cell.Window.window && cell.Window.window.keyFor ? cell.Window.window.keyFor(cell.modelData.job) : "" }
                MouseArea { id: tap; anchors.fill: parent; onClicked: fly.picked(cell.modelData) }
            }
        }
    }
}
