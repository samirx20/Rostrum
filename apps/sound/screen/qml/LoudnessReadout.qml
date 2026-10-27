import QtQuick
import RostrumKit
import "MixFormat.js" as F

// The top bar's loudness against the target (once the song makes a sound), in words and a dot: "Ready for streaming"
// (green, inside ±1 of the target), "Quieter than streaming wants" / "Louder than streaming wants" (amber, never red: it
// is not an error). The number is on hover. The target is the master's own loudness number, always (a target other than
// streaming's −14 says "the target"). A click opens the Mixer, which shows the same with its curve. `compact`: "Ready", "Too quiet".
// While the newest render has failed (backend.soundRefused) the last render's loudness is not the song's: the chip is
// empty (its place kept). What is wrong is said once, in the Problems chip beside it (critic r12 should-fix 8).
Rectangle {
    id: r
    property bool compact: false
    readonly property var target: mixer.loudness.target
    readonly property var lufs: mixer.loudness.lufs      // the last render's, whether or not the Mixer was ever opened
    readonly property var refused: backend.soundRefused
    readonly property bool blocked: !!refused.short
    readonly property bool measured: !blocked && lufs !== undefined && lufs !== null && lufs > -70
    readonly property real goal: mixer.loudness.goal
    readonly property bool near: measured && Math.abs(lufs - goal) <= 1
    readonly property string aim: Math.round(goal) === -14 ? "streaming" : "the target"
    readonly property string said: !measured ? "" : near ? (r.compact ? "Ready" : "Ready for " + aim)
        : lufs < goal ? (r.compact ? "Too quiet" : "Quieter than " + aim + " wants") : (r.compact ? "Too loud" : "Louder than " + aim + " wants")
    // its place is the widest of its words (and the dot), so a new word never moves the top bar's other items
    readonly property real slotWidth: Math.ceil(Math.max(w0.advanceWidth, w1.advanceWidth, w2.advanceWidth, w3.advanceWidth)) + 7 + 3 * Theme.gap
    implicitWidth: slotWidth; implicitHeight: Theme.button
    width: implicitWidth; height: implicitHeight
    TextMetrics { id: w0; font.family: uiFont; font.pixelSize: Theme.body; font.features: { "tnum": 1 }; text: r.compact ? "Loudness …" : "Loudness: rendering…" }
    TextMetrics { id: w1; font: w0.font; text: r.compact ? "Ready" : "Ready for " + r.aim }
    TextMetrics { id: w2; font: w0.font; text: r.compact ? "Too quiet" : "Quieter than " + r.aim + " wants" }
    TextMetrics { id: w3; font: w0.font; text: r.compact ? "Too loud" : "Louder than " + r.aim + " wants" }
    radius: Theme.radiusCtl
    color: area.containsMouse && !r.blocked ? Theme.hover : "transparent"
    Behavior on color { ColorAnimation { duration: Theme.fast } }

    Row {
        id: row
        anchors.centerIn: parent; spacing: Theme.gap
        Rectangle { visible: r.measured; width: 7; height: 7; radius: 3.5
                    anchors.verticalCenter: parent.verticalCenter; color: r.near ? Theme.ok : Theme.warn }
        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: r.blocked ? "" : !r.measured ? (r.compact ? "Loudness …" : "Loudness: rendering…") : r.said
            color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body; font.features: { "tnum": 1 }
        }
    }
    MouseArea { id: area; anchors.fill: parent; enabled: !r.blocked; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: workspace.setDock("mixer") }
    HoverTip { text: (r.measured ? "The whole song is " + F.num(r.lufs, 1) + " LUFS; the target is " + F.num(r.goal, 0) + " LUFS"
                                 : "Measuring the loudness of the whole song") + ". Click to open the Mixer"; hovered: area.containsMouse && !r.blocked }
}
