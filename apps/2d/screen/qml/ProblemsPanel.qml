import QtQuick
import RostrumKit

// Problems: what inspect_diagnose finds in this composition (backend.problems, screen2d/problems.py), each in words
// with how to fix it; a click selects the item it is about. Opened from the top bar's Problems button, which is there
// only while there are any. Same place as the Export and Import panels (one open at a time).
Rectangle {
    id: panel
    property bool shown: false
    readonly property var rows: backend.problems.rows
    width: 340
    height: Theme.header + list.height + Theme.pad
    visible: shown && rows.length > 0
    color: Theme.panel; radius: Theme.radiusPanel
    border.color: Theme.popupEdge
    z: 20

    Text {
        anchors { left: parent.left; leftMargin: Theme.pad; top: parent.top }
        height: Theme.header; verticalAlignment: Text.AlignVCenter
        text: "PROBLEMS"; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.label
        font.weight: Font.DemiBold; font.letterSpacing: Theme.capsSpacing
    }
    ListView {
        id: list
        anchors { left: parent.left; right: parent.right; top: parent.top; topMargin: Theme.header
                  leftMargin: Theme.pad; rightMargin: Theme.pad }
        height: Math.min(contentHeight, 420)
        clip: true; spacing: Theme.gap
        model: panel.rows
        delegate: Rectangle {
            required property var modelData
            width: list.width
            height: body.implicitHeight + 2 * Theme.gap
            radius: Theme.radiusCtl
            color: area.containsMouse && modelData.item ? Theme.hover : "transparent"
            Column {
                id: body
                x: Theme.gap; y: Theme.gap; width: parent.width - 2 * Theme.gap
                spacing: 2
                Text { text: modelData.label; color: modelData.kind === "refused" ? Theme.danger : Theme.warn
                       font.family: uiFont; font.pixelSize: Theme.label; font.weight: Font.DemiBold }
                Text { width: parent.width; text: modelData.message; wrapMode: Text.Wrap
                       color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body }
                Text { width: parent.width; visible: !!modelData.fix; text: modelData.fix; wrapMode: Text.Wrap
                       color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label }
            }
            MouseArea { id: area; anchors.fill: parent; hoverEnabled: true
                        cursorShape: modelData.item ? Qt.PointingHandCursor : Qt.ArrowCursor
                        onClicked: backend.problems.show(modelData.item) }
        }
    }
}
