import QtQuick
import RostrumKit

// The record cluster in the transport strip: one Record / stop button, always the same size, so arming a track moves
// nothing. The state is in the button: its dot is red while a track is armed and pulses while recording, the word
// becomes the take's time (or the count-in), and the microphone's live level is a thin bar along its foot. The take
// panel (count-in, punch, hearing the input, keyboard, "Record keys": RecordSetup.qml) opens on right-click, while armed.
// Ghost style, Theme.field high.
Item {
    id: r
    readonly property bool armed: recorder.armed !== ""
    readonly property bool hasKeys: typeof keys !== "undefined"
    readonly property bool keysOn: hasKeys && keys.recording
    readonly property bool taking: recorder.recording || keysOn
    readonly property int counting: recorder.recording ? recorder.counting : keysOn ? keys.counting : 0
    readonly property int inner: Theme.field
    readonly property string word: r.counting > 0 ? "Count-in " + r.counting
        : recorder.recording ? "Stop " + recorder.elapsed.toFixed(1) + " s"
        : keysOn ? "Stop " + keys.notes + " notes" : "Record"
    implicitWidth: btn.width; implicitHeight: Theme.field
    width: implicitWidth; height: implicitHeight

    TextMetrics { id: widest; font.family: uiFont; font.pixelSize: Theme.label; text: "Stop 000.0 s" }
    Rectangle {   // drawn like the kit's ghost button (no box until hovered)
        id: btn
        anchors.verticalCenter: parent.verticalCenter
        width: Theme.gap + 12 + 2 + widest.width + Theme.gap / 2 + 2; height: r.inner; radius: Theme.radiusCtl
        color: area.pressed ? Theme.active : area.containsMouse ? Theme.hover : "transparent"
        Behavior on color { ColorAnimation { duration: Theme.fast } }
        Rectangle {
            id: dot
            x: Theme.gap - 2; width: 12; height: 12; radius: r.taking ? 2 : 6
            anchors.verticalCenter: parent.verticalCenter
            color: r.armed || r.taking ? Theme.danger : Theme.fg3
            SequentialAnimation on opacity {
                running: r.taking; loops: Animation.Infinite
                NumberAnimation { to: 0.35; duration: 500 }
                NumberAnimation { to: 1; duration: 500 }
                onRunningChanged: if (!running) dot.opacity = 1
            }
        }
        HoverTip { text: r.taking ? "Stop recording (R)" : r.armed ? "Record on the armed track (R). Right-click: how the take is made"
                       : "Record: arms the selected track (or the first that takes sound) and counts in (R)"
                   hovered: area.containsMouse }
        Text { x: Theme.gap + 12 + 2; anchors.verticalCenter: parent.verticalCenter
               text: r.word; font.family: uiFont; font.pixelSize: Theme.label; font.features: { "tnum": 1 }
               color: Theme.fg }
        Rectangle {   // the microphone's peak, -60 … 0 dBFS (the engine's {"input"} level), along the foot of the button
            id: level
            visible: r.armed && typeof recorder.level === "number"
            x: Theme.gap; y: parent.height - 4; height: 2; radius: 1; width: parent.width - 2 * Theme.gap
            color: Theme.sunken
            readonly property real db: typeof recorder.level === "number" ? recorder.level : -100
            Rectangle { height: parent.height; radius: 1
                        width: parent.width * Math.max(0, Math.min(1, (level.db + 60) / 60))
                        color: level.db > -1 ? Theme.danger : level.db > -6 ? Theme.warn : Theme.ok }
        }
        MouseArea { id: area; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    acceptedButtons: Qt.LeftButton | Qt.RightButton
                    onClicked: (m) => {
                        if (m.button === Qt.RightButton) { if (r.armed && !r.taking) takeSetup.setOpen(!takeSetup.open) }
                        else if (r.keysOn) keys.toggleRecord()
                        else recorder.toggleRecord()
                    } }
        RecordSetup { y: btn.height + 6 }
    }
}
