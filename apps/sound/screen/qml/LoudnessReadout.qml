import QtQuick
import RostrumKit
import "MixFormat.js" as F

// The top bar's loudness against the target (once the song makes a sound): "−15.2 LUFS · target −14" and a dot,
// green inside ±1 of the target, amber outside (never red: it is not an error). The target is the master's own
// loudness number, always. Click: the Mixer, with the master's loudness curve. `compact` (a small window): "−15.2 LUFS · −14".
Rectangle {
    id: r
    property bool compact: false
    readonly property var target: mixer.loudness.target
    readonly property var lufs: mixer.master.meter ? mixer.master.meter.lufs : undefined
    readonly property bool measured: lufs !== undefined && lufs !== null && lufs > -70
    readonly property real goal: mixer.loudness.goal
    readonly property bool near: measured && Math.abs(lufs - goal) <= 1
    implicitWidth: row.implicitWidth + 2 * Theme.gap; implicitHeight: Theme.button
    width: implicitWidth; height: implicitHeight
    radius: Theme.radiusCtl
    color: area.containsMouse ? Theme.hover : "transparent"
    Behavior on color { ColorAnimation { duration: Theme.fast } }

    Row {
        id: row
        anchors.centerIn: parent; spacing: Theme.gap
        Rectangle { visible: r.measured; width: 7; height: 7; radius: 3.5
                    anchors.verticalCenter: parent.verticalCenter; color: r.near ? Theme.ok : Theme.warn }
        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: !r.measured ? (r.compact ? "LUFS …" : "Loudness: rendering…")
                  : F.num(r.lufs, 1) + " LUFS" + (r.compact ? " · " : "  ·  target ") + F.num(r.goal, 0)
            color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body; font.features: { "tnum": 1 }
        }
    }
    MouseArea { id: area; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                onClicked: workspace.setDock("mixer") }
    HoverTip { text: "Loudness (LUFS) of the whole song, against the master's target of " + F.num(r.goal, 0)
                     + ". Click: the Mixer"; hovered: area.containsMouse }
}
