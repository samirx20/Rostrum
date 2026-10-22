import QtQuick
import RostrumKit

// The record cluster in the top bar, one framed group so it reads as one thing: Record / stop, the "Take" panel
// (count-in, punch, hearing the input, keyboard: RecordSetup.qml), the microphone's live level (the engine's input
// level, while the track is armed), the take's time or count-in, and "Record keys" when a MIDI keyboard is connected
// and the armed track takes notes. Absent unless a track is armed (nothing greyed out). All its buttons are the
// kit's ghost style.
Rectangle {
    id: r
    visible: recorder.armed !== ""
    readonly property bool hasKeys: typeof keys !== "undefined"
    readonly property bool keysOn: hasKeys && keys.recording
    readonly property bool taking: recorder.recording || keysOn
    readonly property int counting: recorder.recording ? recorder.counting : keysOn ? keys.counting : 0
    readonly property int inner: Theme.button - 4
    implicitWidth: row.implicitWidth + 4; implicitHeight: Theme.button
    width: implicitWidth; height: implicitHeight
    radius: Theme.radiusCtl; color: "transparent"
    border.width: 1; border.color: r.taking ? Qt.rgba(Theme.danger.r, Theme.danger.g, Theme.danger.b, 0.6) : Theme.line

    Row {
        id: row
        anchors.centerIn: parent
        spacing: 2
        Rectangle {   // Record / stop: drawn like the kit's ghost button (no box until hovered)
            visible: !r.keysOn
            width: recWord.x + recWord.width + Theme.gap / 2 + 2; height: r.inner; radius: Theme.radiusCtl
            color: area.pressed ? Theme.active : area.containsMouse ? Theme.hover : "transparent"
            Behavior on color { ColorAnimation { duration: Theme.fast } }
            Rectangle { color: Theme.danger
                        x: Theme.gap - 2; width: 12; height: 12; radius: recorder.recording ? 2 : 6
                        anchors.verticalCenter: parent.verticalCenter }
            Text { id: recWord; x: Theme.gap + 12 + 2; anchors.verticalCenter: parent.verticalCenter
                   text: recorder.recording ? "Stop" : "Record"; font.family: uiFont; font.pixelSize: Theme.label
                   color: Theme.fg }
            MouseArea { id: area; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onClicked: recorder.toggleRecord() }
        }
        Button {
            id: takeButton
            visible: !r.taking; text: "Take"; kind: "ghost"; down: takeSetup.open; height: r.inner
            onClicked: takeSetup.setOpen(!takeSetup.open)
            RecordSetup { y: takeButton.height + 6 }
        }
        Item {        // the input level (and the take's time): one slot, so the cluster does not jump
            visible: recorder.level !== null || r.taking
            width: (recorder.level !== null ? level.width + Theme.gap : 0) + (r.taking ? status.implicitWidth + Theme.gap : 0)
            height: r.inner
            Rectangle {   // the microphone's peak, -60 … 0 dBFS, sideways (the engine's {"input"} level)
                id: level
                visible: typeof recorder.level === "number"     // none (null / undefined): no microphone level yet
                x: Theme.gap; anchors.verticalCenter: parent.verticalCenter
                width: 24; height: 6; radius: 3; color: Theme.sunken
                readonly property real db: typeof recorder.level === "number" ? recorder.level : -100
                Rectangle { height: parent.height; radius: 3
                            width: parent.width * Math.max(0, Math.min(1, (level.db + 60) / 60))
                            color: level.db > -1 ? Theme.danger : level.db > -6 ? Theme.warn : Theme.ok }
            }
            Text {
                id: status
                visible: r.taking; anchors.verticalCenter: parent.verticalCenter; anchors.right: parent.right
                anchors.rightMargin: Theme.gap / 2
                text: r.counting > 0 ? "Count-in " + r.counting
                    : recorder.recording ? "REC " + recorder.elapsed.toFixed(1) + " s" : "Keys " + keys.notes + " notes"
                font.family: monoFont; font.pixelSize: Theme.label; color: Theme.danger
            }
        }
        // Keyboard take (keys_record.py): only with a keyboard and a notes / drum track, and not during a microphone take.
        Button {
            visible: r.hasKeys && keys.usable && !recorder.recording
            text: r.keysOn ? "Stop keys" : "Record keys"; kind: "ghost"; height: r.inner
            onClicked: keys.toggleRecord()
        }
    }
}
