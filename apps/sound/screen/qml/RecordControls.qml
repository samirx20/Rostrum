import QtQuick
import RostrumKit

// Record / stop, a live level meter and the take's time. Absent unless a track is armed (nothing greyed out).
Row {
    id: r
    visible: recorder.armed !== ""
    spacing: Theme.gap

    Rectangle {
        implicitWidth: Theme.button; implicitHeight: Theme.button; width: implicitWidth; height: implicitHeight
        radius: Theme.radiusCtl
        color: area.pressed ? Theme.active : area.containsMouse ? Theme.hover : Theme.raised
        Behavior on color { ColorAnimation { duration: Theme.fast } }
        Rectangle { anchors.centerIn: parent; color: Theme.danger
                    width: 12; height: 12; radius: recorder.recording ? 2 : 6 }
        MouseArea { id: area; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    onClicked: recorder.toggleRecord() }
    }
    MixMeter { visible: recorder.recording; peak: recorder.level; height: Theme.button; anchors.verticalCenter: parent.verticalCenter }
    Text {
        visible: recorder.recording; anchors.verticalCenter: parent.verticalCenter
        text: "REC " + recorder.elapsed.toFixed(1) + " s"
        font.family: monoFont; font.pixelSize: Theme.label; color: Theme.danger
    }
}
