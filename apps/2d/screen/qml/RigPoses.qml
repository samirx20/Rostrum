import QtQuick
import RostrumKit

// The settings panel's "Poses" group while a rig is in hand (UX_SPEC 3.23 › Pose library; backend.poses:
// screen2d/rig_poses.py). Save pose keeps the pose at the playhead; a click on a pose keys it there; its slider goes
// part of the way from the pose there now (one change on release); right-click › Delete. Absent without a rig.
Column {
    id: pl
    readonly property var p: backend.poses
    width: parent ? parent.width : 0
    visible: p.rig !== ""
    spacing: 2

    Item {  // the heading, like a group's, with Save pose at its right
        width: pl.width; height: Theme.groupGap + Theme.row
        Text {
            anchors { left: parent.left; bottom: parent.bottom; bottomMargin: Theme.grid + 4 }
            text: "Poses"; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label; font.weight: Font.DemiBold
        }
        Button {
            anchors { right: parent.right; bottom: parent.bottom }
            text: "Save pose"; help: "Pose the character on the canvas, then keep its pose at the playhead in the library."
            onClicked: pl.p.save()
        }
    }
    Repeater {
        model: pl.p.poses
        delegate: Rectangle {
            id: row
            required property var modelData
            width: pl.width; height: Theme.row; radius: Theme.radiusCtl
            color: rowArea.containsMouse ? Theme.hover : "transparent"
            Text {
                anchors { left: parent.left; leftMargin: Theme.grid; verticalCenter: parent.verticalCenter }
                width: parent.width * 0.45; elide: Text.ElideRight
                text: row.modelData.name; color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body
            }
            MouseArea {
                id: rowArea
                anchors { left: parent.left; top: parent.top; bottom: parent.bottom }
                width: parent.width * 0.5
                hoverEnabled: true; acceptedButtons: Qt.LeftButton | Qt.RightButton
                onClicked: (m) => {
                    if (m.button === Qt.RightButton) { const g = rowArea.mapToItem(null, m.x, m.y); poseMenu.pose = row.modelData.id; poseMenu.openAt(g.x, g.y) }
                    else pl.p.apply(row.modelData.id)
                }
            }
            HoverTip { hovered: rowArea.containsMouse; text: "Click: key this pose at the playhead" }
            Slider {
                anchors { right: parent.right; rightMargin: Theme.grid; verticalCenter: parent.verticalCenter }
                width: parent.width * 0.45
                from: 0; to: 1; value: row.modelData.amount
                onScrubbed: (v) => pl.p.blendTo(row.modelData.id, v)
                onEdited: (v) => { pl.p.blendTo(row.modelData.id, v); pl.p.endBlend() }
                onScrubEnded: pl.p.endBlend()
            }
        }
    }
    ActionMenu {
        id: poseMenu
        property string pose: ""
        entries: [{ value: "delete", label: "Delete pose" }]
        onPicked: (v) => pl.p.remove(pose)
    }
}
