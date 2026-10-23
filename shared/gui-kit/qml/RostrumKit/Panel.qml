import QtQuick
import "."

// A rounded panel. Panels are told apart by background steps, not lines, and fixed areas carry no caption:
// the header row exists only for a sheet's title (with its ×, `headerRight`); with no title and no header
// buttons the body starts at the top. Children go into the body (padded).
// `sheets`: panels that take this panel's place while shown (2D: Lip sync on the settings panel); while any of them is
// visible the panel's own header and body are hidden (off screen means out of reach: keys, the layout check).
Rectangle {
    id: panel
    property string title: ""
    property alias headerRight: headerRightSlot.data
    default property alias body: content.data
    property alias sheets: sheetSlot.data
    readonly property bool sheetShown: { for (const c of sheetSlot.children) if (c.visible) return true; return false }
    property int bodyPad: Theme.pad
    property int bodyRight: bodyPad          // the body's right margin (a sheet in the settings column: Theme.fieldEdge)
    color: Theme.panel
    radius: Theme.radiusPanel
    clip: true

    Item {
        id: header
        visible: !panel.sheetShown && height > 0
        anchors { left: parent.left; right: parent.right; top: parent.top }
        height: panel.title !== "" || headerRightSlot.children.length > 0 ? Theme.header : 0
        Text {
            anchors.left: parent.left; anchors.leftMargin: Theme.pad; anchors.verticalCenter: parent.verticalCenter
            anchors.right: headerRightSlot.left; anchors.rightMargin: Theme.gap
            text: panel.title; color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body
            font.weight: Font.DemiBold; elide: Text.ElideRight
        }
        Row {
            id: headerRightSlot
            anchors.right: parent.right; anchors.rightMargin: Theme.gap; anchors.verticalCenter: parent.verticalCenter
            spacing: Theme.grid
        }
    }
    Item {
        id: content
        visible: !panel.sheetShown
        anchors { left: parent.left; right: parent.right; top: header.bottom; bottom: parent.bottom
                  topMargin: header.height > 0 ? 0 : panel.bodyPad
                  leftMargin: panel.bodyPad; rightMargin: panel.bodyRight; bottomMargin: panel.bodyPad }
    }
    property var _wired: []                 // one sheet at a time: a sheet that shows closes the others (their close())
    Item {
        id: sheetSlot; anchors.fill: parent
        onChildrenChanged: {
            for (const c of children) {
                if (panel._wired.indexOf(c) >= 0) continue
                panel._wired.push(c)
                c.visibleChanged.connect(() => {
                    if (!c.visible) return
                    for (const o of sheetSlot.children)
                        if (o !== c && o.visible && typeof o.close === "function") o.close()
                })
            }
        }
    }
}
