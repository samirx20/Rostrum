import QtQuick
import RostrumKit

// The top of the settings panel while painting (painting design §2.1, mockup paint-01): the heading "Brush" and the
// brush's name as a plain label ▾; a click opens the brush panel (BrushFlyout.qml), the one place a brush is chosen. Only
// while the Brush or Eraser is the tool (painter.toolParts). The quick rows follow (the Inspector's, brush.py TOOL_PARTS). While editing the brush
// (Edit brush ›) this is "‹ Back" instead, with "+ Save this brush" at its right (SaveBrush.qml: into My brushes),
// and the rows are every brush setting.
Column {
    id: head
    width: parent ? parent.width : 0
    readonly property bool editing: painter.editing
    readonly property var brush: painter.brushNow
    readonly property bool shown: !head.editing && painter.toolParts.brush      // Fill, Pick and Select have no brush of their own

    Item {     // the heading, as the panel's group headings
        visible: head.shown
        width: head.width; height: Theme.rowDense
        Text { anchors.left: parent.left; anchors.bottom: parent.bottom; anchors.bottomMargin: Theme.grid + 2
               text: "Brush"; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label; font.weight: Font.DemiBold }
    }
    Item {    // the brush: its name as a plain label; a click opens the brush panel, the one place a brush is chosen
        objectName: "brushRow"
        visible: head.shown
        width: head.width; height: Theme.row
        Rectangle { width: Theme.wideFor(head.width); height: parent.height; radius: Theme.radiusCtl; color: Theme.hover; visible: rowArea.containsMouse }
        Text {
            anchors { left: parent.left; leftMargin: 0; right: chev.left; rightMargin: Theme.grid; verticalCenter: parent.verticalCenter }
            elide: Text.ElideRight
            text: head.brush.name || ""; color: rowArea.containsMouse ? Theme.fg : Theme.fg2
            font.family: uiFont; font.pixelSize: Theme.body
        }
        Chevron { id: chev; x: Theme.wideFor(head.width) - width - Theme.grid; anchors.verticalCenter: parent.verticalCenter
                  color: rowArea.containsMouse ? Theme.fg : Theme.fg3 }
        MouseArea { id: rowArea; width: Theme.wideFor(head.width); height: parent.height; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    onClicked: head.Window.window.openFlyout("brush") }
    }
    Item { visible: head.shown; width: 1; height: Theme.grid }
    Item {     // editing the brush: back to painting
        objectName: "brushBack"
        visible: head.editing
        width: head.width; height: Theme.row
        Rectangle { anchors { left: parent.left; top: parent.top; bottom: parent.bottom; right: save.left }
                    radius: Theme.radiusCtl; color: Theme.hover; visible: backArea.containsMouse }
        Chevron { id: back; anchors.left: parent.left; anchors.leftMargin: Theme.grid; anchors.verticalCenter: parent.verticalCenter
                  rotation: 90; color: Theme.fg }
        Text { anchors.left: back.right; anchors.leftMargin: Theme.grid + 2; anchors.verticalCenter: parent.verticalCenter
               text: "Back"; color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body }
        MouseArea { id: backArea; anchors { left: parent.left; top: parent.top; bottom: parent.bottom; right: save.left }
                    hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: painter.setEditing(false) }
        SaveBrush { id: save; anchors { right: parent.right; rightMargin: Theme.keyGutter - 4; verticalCenter: parent.verticalCenter }
                    width: naming ? Theme.fieldFor(head.width) : implicitWidth }
    }
}
