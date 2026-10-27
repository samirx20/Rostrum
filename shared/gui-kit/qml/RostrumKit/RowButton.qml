import QtQuick
import "."

// A small button at the right of a settings row's field (InspectorRow, model.button = {label, id, menu}). One action: a
// click runs it (bridge.rowAction(id)). A `menu` ([{value, label}]): a click opens it and a pick runs that action. It is as
// tall as a field and as wide as its word (a chevron after it when it opens a menu), so the row keeps its grid.
Rectangle {
    id: b
    property string text: ""
    property var menu: []
    property bool working: false         // what its click started is still running (ack.py): it stays pressed
    readonly property bool hasMenu: !!(menu && menu.length)
    signal chosen(string id)
    implicitWidth: label.implicitWidth + (hasMenu ? 16 : 0) + 2 * Theme.gap
    implicitHeight: Theme.field
    radius: Theme.radiusCtl
    color: area.containsMouse ? Theme.hover : Theme.raised          // the hover fades in ...
    Behavior on color { ColorAnimation { duration: Theme.fast } }
    Rectangle { anchors.fill: parent; radius: parent.radius; color: Theme.active     // ... the press never does
                visible: area.pressed || choices.visible || b.working }
    Text { id: label; x: Theme.gap; anchors.verticalCenter: parent.verticalCenter; text: b.text; color: Theme.fg
           font.pixelSize: Theme.body; font.family: uiFont }
    Chevron { visible: b.hasMenu; open: choices.visible; anchors.verticalCenter: parent.verticalCenter
              anchors.right: parent.right; anchors.rightMargin: Theme.grid; color: Theme.fg2 }
    MouseArea {
        id: area; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
        onClicked: {
            if (!b.hasMenu) { if (typeof ack !== "undefined" && ack) ack.by(b); b.chosen(""); return }
            const p = b.mapToItem(choices.parent, 0, b.height + 2)
            choices.openAt(p.x, p.y)
        }
    }
    ActionMenu { id: choices; entries: b.menu || []; onPicked: v => b.chosen(v) }
}
