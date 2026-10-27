import QtQuick
import RostrumKit
import "MixFormat.js" as F

// The top bar's loudness chip against the target (once the song makes a sound), short words and a dot at every window
// width: "On target" (green, inside ±1 of the target), "Too quiet" / "Too loud" (amber, never red: it is not an error).
// The sentence ("Quieter than streaming wants") and the number are on hover. The target is the master's own loudness
// number, always (a target other than streaming's −14 says "the target"). A click opens the Mixer, which shows the same
// with its curve.
// While the newest render has failed (backend.soundRefused) the last render's loudness is not the song's: the chip is
// empty (its place kept). What is wrong is said once, in the Problems chip beside it (critic r12 should-fix 8).
Rectangle {
    id: r
    readonly property var target: mixer.loudness.target
    readonly property var lufs: mixer.loudness.lufs      // the last render's, whether or not the Mixer was ever opened
    readonly property var refused: backend.soundRefused
    readonly property bool blocked: !!refused.short
    readonly property bool rendered: !blocked && lufs !== undefined && lufs !== null && lufs > -70
    // A loudness number needs music to average: one note's sound is a few hundred milliseconds of the loudest part, and
    // "Quieter than streaming wants" on it is noise. The chip stays empty (its place kept) until the render
    // has this many seconds of sound in it; the Mixer and the export sheet show the number whenever there is one.
    readonly property real enoughSeconds: 5
    readonly property bool measured: rendered && mixer.loudness.heardSeconds >= enoughSeconds
    readonly property bool tooShort: rendered && !measured
    readonly property real goal: mixer.loudness.goal
    readonly property bool near: measured && Math.abs(lufs - goal) <= 1
    readonly property string aim: Math.round(goal) === -14 ? "streaming" : "the target"
    readonly property string said: !measured ? "" : near ? "On target" : lufs < goal ? "Too quiet" : "Too loud"
    readonly property string sentence: !measured ? "" : near ? "Ready for " + aim
        : lufs < goal ? "Quieter than " + aim + " wants" : "Louder than " + aim + " wants"
    // its place is the widest of its words (and the dot), so a new word never moves the top bar's other items
    readonly property real slotWidth: Math.ceil(Math.max(w0.advanceWidth, w1.advanceWidth, w2.advanceWidth, w3.advanceWidth)) + 7 + 3 * Theme.gap
    implicitWidth: slotWidth; implicitHeight: Theme.button
    width: implicitWidth; height: implicitHeight
    TextMetrics { id: w0; font.family: uiFont; font.pixelSize: Theme.label; text: "Loudness …" }
    TextMetrics { id: w1; font: w0.font; text: "On target" }
    TextMetrics { id: w2; font: w0.font; text: "Too quiet" }
    TextMetrics { id: w3; font: w0.font; text: "Too loud" }
    radius: Theme.radiusCtl
    color: r.blocked || r.tooShort ? "transparent" : area.containsMouse ? Theme.hover : Theme.raised     // a chip, as the bar's others
    Behavior on color { ColorAnimation { duration: Theme.fast } }

    Row {
        id: row
        anchors.centerIn: parent; spacing: Theme.gap
        Rectangle { visible: r.measured; width: 7; height: 7; radius: 3.5
                    anchors.verticalCenter: parent.verticalCenter; color: r.near ? Theme.ok : Theme.warn }
        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: r.blocked || r.tooShort ? "" : !r.measured ? "Loudness …" : r.said
            color: Theme.fg; font: w0.font
        }
    }
    MouseArea { id: area; anchors.fill: parent; enabled: !r.blocked && !r.tooShort; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: workspace.setDock("mixer") }
    HoverTip { text: r.measured ? r.sentence : "Measuring the loudness of the whole song"
               help: (r.measured ? "The whole song is " + F.num(r.lufs, 1) + " LUFS; the target is " + F.num(r.goal, 0) + " LUFS. " : "")
                     + "Click to open the Mixer."
               hovered: area.containsMouse && !r.blocked && !r.tooShort }
}
