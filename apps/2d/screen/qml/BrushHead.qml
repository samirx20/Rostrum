import QtQuick
import RostrumKit

// The top of the settings panel while painting (painting design §2.1, mockup paint-01): the heading "Brush" and the
// brush's own wide row, its stroke (painted by the engine, image://brushes) and its name ▾; a click opens the brush
// panel (BrushFlyout.qml). The quick rows follow (the Inspector's, brush.py QUICK). While editing the brush
// (Edit brush ›) this is "‹ Back" instead, with "+ Save this brush" at its right (SaveBrush.qml: into My brushes),
// and the rows are every brush setting.
Column {
    id: head
    width: parent ? parent.width : 0
    readonly property bool editing: painter.editing
    readonly property var brush: painter.brushNow

    Item {     // the heading, as the panel's group headings
        visible: !head.editing
        width: head.width; height: Theme.rowDense
        Text { anchors.left: parent.left; anchors.bottom: parent.bottom; anchors.bottomMargin: Theme.grid + 2
               text: "Brush"; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label; font.weight: Font.DemiBold }
    }
    Rectangle {    // the brush: its stroke and its name ▾
        objectName: "brushRow"
        visible: !head.editing && backend.paintTool.now !== "fill"
        width: Theme.wideFor(head.width); height: 44; radius: Theme.radiusCtl
        color: rowArea.containsMouse ? Theme.hover : Theme.raised
        border.color: Theme.popupEdge
        Image {
            x: 4; y: 4; width: parent.width * 0.6; height: parent.height - 8
            source: head.brush.preset ? "image://brushes/" + head.brush.preset : ""
            asynchronous: true; fillMode: Image.PreserveAspectCrop; smooth: true; mipmap: true
        }
        Text {
            anchors { right: chev.left; rightMargin: Theme.grid; verticalCenter: parent.verticalCenter }
            width: parent.width * 0.4 - 24 - Theme.grid; horizontalAlignment: Text.AlignRight; elide: Text.ElideRight
            text: head.brush.name || ""; color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body
        }
        Chevron { id: chev; anchors { right: parent.right; rightMargin: Theme.gap; verticalCenter: parent.verticalCenter }
                  color: rowArea.containsMouse ? Theme.fg : Theme.fg3 }
        MouseArea { id: rowArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    onClicked: head.Window.window.openFlyout("brush") }
    }
    Item { visible: !head.editing; width: 1; height: Theme.grid }
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
