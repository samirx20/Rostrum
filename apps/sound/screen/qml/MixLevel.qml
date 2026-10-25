import QtQuick
import RostrumKit
import "MixFormat.js" as F

// A strip's level block, left to right: the dB scale, the fader, the meter with its peak number above it. The scale
// and the meter sit on the fader's own travel (inset by half the knob), so their marks line up with the knob. While the
// song plays the meter moves with the sound (`live`, from the engine); the number is the highest peak since play
// started (`peak`, one rule for tracks, groups and the Master), held after the stop while the meter falls to silence.
Item {
    id: lv
    property real gain: 1
    property string ownerId: ""         // the strip's: the fader is named "mixFader:" + it (a scripted hand finds it)
    property var meter: ({})            // {peak, lufs} from the last render, or {}: not measured
    property var live: null             // [peak dB, RMS dB] while playing (mixer.live), else null
    signal scrubStarted()
    signal scrubbed(real gain)
    signal scrubEnded()
    signal reset()
    signal typeIt()
    signal nudged(real gain)
    property var peak: null             // dBFS: the highest peak since play started (mixer.peaks), held after the stop; null: none yet
    readonly property var shown: peak !== null && peak > F.FLOOR ? peak : null
    implicitWidth: scale.width + fader.width + meterBar.width + 2 * Theme.grid
    Text {   // the peak since play started, held after the stop ("−∞": silent so far; nothing: not played yet)
        id: peakText
        anchors.horizontalCenter: meterBar.horizontalCenter; anchors.top: parent.top
        text: lv.shown !== null ? F.num(lv.shown, 1) : lv.peak !== null || lv.live ? "−∞" : ""
        color: lv.shown !== null ? Theme[F.levelTone(lv.shown)] : Theme.fg3
        font.family: uiFont; font.pixelSize: Theme.label; font.features: { "tnum": 1 }
    }
    MixScale { id: scale; anchors { left: parent.left; top: fader.top; bottom: fader.bottom } inset: 7 }
    MixFader {
        id: fader
        objectName: "mixFader:" + lv.ownerId
        anchors { left: scale.right; leftMargin: Theme.grid; top: peakText.bottom; topMargin: 2; bottom: parent.bottom }
        width: 28; gain: lv.gain
        onScrubStarted: lv.scrubStarted()
        onScrubbed: (g) => lv.scrubbed(g)
        onScrubEnded: lv.scrubEnded()
        onReset: lv.reset()
        onTypeIt: lv.typeIt()
        onNudged: (g) => lv.nudged(g)
    }
    MixMeter {
        id: meterBar
        anchors { left: fader.right; leftMargin: Theme.grid; top: fader.top; bottom: fader.bottom; topMargin: 7; bottomMargin: 7 }
        live: lv.live
        tip: lv.live ? "Level now: the bar is the average (RMS), the thin bar and the mark the peak. The number is the highest peak since play started"
             : lv.peak !== null ? "Highest peak of the last play: " + (lv.shown !== null ? F.num(lv.shown, 1) + " dB" : "silent") + ". Play to start again"
             : "Play to see the level move"
    }
}
