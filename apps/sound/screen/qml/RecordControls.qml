import QtQuick
import RostrumKit

// Record / stop, the "Take" panel (count-in, punch, input level, keyboard: RecordSetup.qml), a live level meter
// (during a take, or while "Input level" is on) and the take's time or count-in; "Record keys" when a MIDI keyboard
// is connected and the armed track takes notes. Absent unless a track is armed (nothing greyed out).
Row {
    id: r
    visible: recorder.armed !== ""
    spacing: Theme.gap
    readonly property bool hasKeys: typeof keys !== "undefined"
    readonly property bool keysOn: hasKeys && keys.recording
    readonly property bool taking: recorder.recording || keysOn
    readonly property int counting: recorder.recording ? recorder.counting : keysOn ? keys.counting : 0

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
    Button {
        id: takeButton
        visible: !r.taking; text: "Take"; kind: "ghost"; down: takeSetup.open
        anchors.verticalCenter: parent.verticalCenter
        onClicked: takeSetup.setOpen(!takeSetup.open)
        RecordSetup { y: takeButton.height + 4 }
    }
    MixMeter { visible: recorder.level !== null; peak: recorder.level; height: Theme.button; anchors.verticalCenter: parent.verticalCenter }
    Text {
        visible: r.taking; anchors.verticalCenter: parent.verticalCenter
        text: r.counting > 0 ? "Count-in " + r.counting
            : recorder.recording ? "REC " + recorder.elapsed.toFixed(1) + " s" : "Keys  " + keys.notes + " notes"
        font.family: monoFont; font.pixelSize: Theme.label; color: Theme.danger
    }
    // Keyboard take (keys_record.py): only with a keyboard and a notes / drum track, and not during a microphone take.
    Rectangle {
        visible: r.hasKeys && keys.usable && !recorder.recording
        implicitWidth: keysLabel.implicitWidth + 16; implicitHeight: Theme.button; width: implicitWidth; height: implicitHeight
        radius: Theme.radiusCtl
        color: keysArea.pressed ? Theme.active : keysArea.containsMouse ? Theme.hover : Theme.raised
        Text { id: keysLabel; anchors.centerIn: parent; font.family: uiFont; font.pixelSize: Theme.label
               text: r.keysOn ? "Stop keys" : "Record keys"
               color: r.keysOn ? Theme.danger : Theme.fg2 }
        MouseArea { id: keysArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    onClicked: keys.toggleRecord() }
    }
}
