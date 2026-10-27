import QtQuick
import RostrumKit

// The settings panel while Pose is on (screen3d/pose_qt.py): "Posing" and the clay's name, then three short rows:
// Joints (how many, Find again), Names (Plain / Humanoid), Holds (how many, Clear when there are any). Each button one
// undo step, the same operations agents call (ops_pose). Nothing else: the canvas is where posing happens.
Item {
    id: panel
    objectName: "posePanel"
    readonly property var p: viewport.pose
    readonly property int labelW: 64
    Column {
        id: col
        anchors { left: parent.left; right: parent.right; top: parent.top; margins: Theme.pad }
        spacing: Theme.gap

        Row {
            width: parent.width; spacing: Theme.grid
            Text { text: "Posing"; color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body; font.weight: Font.DemiBold
                   anchors.verticalCenter: parent.verticalCenter }
            Text { text: panel.p.itemName; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.body
                   elide: Text.ElideRight; width: parent.width - 80; anchors.verticalCenter: parent.verticalCenter }
        }
        Row {
            width: parent.width; height: Theme.button; spacing: Theme.grid
            Text { width: panel.labelW; text: "Joints"; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.body
                   anchors.verticalCenter: parent.verticalCenter }
            Text { objectName: "poseJointCount"; width: parent.width - panel.labelW - findBtn.width - 2 * Theme.grid
                   text: panel.p.joints; color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body
                   font.features: { "tnum": 1 }; anchors.verticalCenter: parent.verticalCenter }
            Button { id: findBtn; objectName: "poseFindAgain"; text: "Find again"; kind: "ghost"
                     help: "Find the joints from the clay's shape again; joints you placed and bends stay."
                     anchors.verticalCenter: parent.verticalCenter; onClicked: panel.p.findAgain() }
        }
        Row {
            width: parent.width; height: Theme.button; spacing: Theme.grid
            Text { width: panel.labelW; text: "Names"; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.body
                   anchors.verticalCenter: parent.verticalCenter }
            Segmented { objectName: "poseNames"; anchors.verticalCenter: parent.verticalCenter
                        options: [{ value: "plain", label: "Plain" }, { value: "humanoid", label: "Humanoid" }]
                        current: panel.p.names; onPicked: (v) => panel.p.setNames(v) }
        }
        Row {
            width: parent.width; height: Theme.button; spacing: Theme.grid
            Text { width: panel.labelW; text: "Holds"; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.body
                   anchors.verticalCenter: parent.verticalCenter }
            Text { objectName: "poseHoldCount"; width: parent.width - panel.labelW - clearBtn.width - 2 * Theme.grid
                   text: panel.p.holds; color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body
                   font.features: { "tnum": 1 }; anchors.verticalCenter: parent.verticalCenter }
            Button { id: clearBtn; objectName: "poseClearHolds"; text: "Clear"; kind: "ghost"; visible: panel.p.holds > 0
                     help: "Let go of every hold on this clay."
                     anchors.verticalCenter: parent.verticalCenter; onClicked: panel.p.clearHolds() }
        }
    }
}
