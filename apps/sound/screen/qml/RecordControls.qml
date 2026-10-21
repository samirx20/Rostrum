import QtQuick
import RostrumKit

// Record / stop, a live level meter and the take's time; "Record keys" when a MIDI keyboard is connected.
// Absent unless a track is armed (nothing greyed out).
Row {
    id: r
    visible: recorder.armed !== ""
    spacing: Theme.gap
    readonly property bool hasKeys: typeof keys !== "undefined"
    readonly property bool keysOn: hasKeys && keys.recording

    Rectangle {
        visible: !r.keysOn
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
    // Keyboard take (keys_record.py): only when a MIDI keyboard is connected, and not during a microphone take.
    Rectangle {
        visible: r.hasKeys && keys.devices.length > 0 && !recorder.recording
        implicitWidth: keysLabel.implicitWidth + 16; implicitHeight: Theme.button; width: implicitWidth; height: implicitHeight
        radius: Theme.radiusCtl
        color: keysArea.pressed ? Theme.active : keysArea.containsMouse ? Theme.hover : Theme.raised
        Text { id: keysLabel; anchors.centerIn: parent; font.family: uiFont; font.pixelSize: Theme.label
               text: r.keysOn ? "Stop keys  " + keys.notes : "Record keys"
               color: r.keysOn ? Theme.danger : Theme.fg2 }
        MouseArea { id: keysArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    onClicked: keys.toggleRecord() }
    }
}
