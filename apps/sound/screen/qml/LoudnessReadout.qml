import QtQuick
import RostrumKit
import "MixFormat.js" as F

// The top bar's loudness against the target (once the song makes a sound): "Loudness −15.2 · target −14" and a dot,
// green inside ±1 of the target, amber outside (never red: it is not an error). No target chosen: the loudness alone.
// Click: the Mixer, with the master's loudness curve. `compact` (a small window): "Loudness −15.2 · −14".
Rectangle {
    id: r
    property bool compact: false
    readonly property var target: mixer.loudness.target
    readonly property var lufs: mixer.master.meter ? mixer.master.meter.lufs : undefined
    readonly property bool measured: lufs !== undefined && lufs !== null && lufs > -70
    readonly property bool hasTarget: !!target.shown && target.lufs !== null && target.lufs !== undefined
    readonly property bool near: hasTarget && measured && Math.abs(lufs - target.lufs) <= 1
    implicitWidth: row.implicitWidth + 2 * Theme.gap; implicitHeight: Theme.button
    width: implicitWidth; height: implicitHeight
    radius: Theme.radiusCtl
    color: area.containsMouse ? Theme.hover : "transparent"
    Behavior on color { ColorAnimation { duration: Theme.fast } }

    Row {
        id: row
        anchors.centerIn: parent; spacing: Theme.gap
        Rectangle { visible: r.hasTarget && r.measured; width: 7; height: 7; radius: 3.5
                    anchors.verticalCenter: parent.verticalCenter; color: r.near ? Theme.ok : Theme.warn }
        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: !r.measured ? (r.compact ? "Loudness …" : "Loudness: rendering…")
                  : "Loudness " + F.num(r.lufs, 1)
                    + (r.hasTarget ? (r.compact ? " · " : "  ·  target ") + F.num(r.target.lufs, 0) : "")
            color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body; font.features: { "tnum": 1 }
        }
    }
    MouseArea { id: area; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                onClicked: workspace.setDock("mixer") }
    HoverTip { text: "Loudness (LUFS) of the whole song" + (r.hasTarget ? ", against the delivery target" : "")
                     + ". Click: the Mixer"; hovered: area.containsMouse }
}
