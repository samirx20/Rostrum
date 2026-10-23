import QtQuick
import RostrumKit
import "MixFormat.js" as F

// A strip's level block, left to right: the dB scale, the fader, the meter with its peak number above it. The scale
// and the meter sit on the fader's own travel (inset by half the knob), so their marks line up with the knob. While the
// song plays the meter moves with the sound (`live`, from the engine) and the number is its held peak; stopped, the
// meter falls to silence and the number is the last render's highest level.
Item {
    id: lv
    property real gain: 1
    property var meter: ({})            // {peak, lufs} from the last render, or {}: not measured
    property var live: null             // [peak dB, RMS dB] while playing (mixer.live), else null
    signal scrubStarted()
    signal scrubbed(real gain)
    signal scrubEnded()
    signal reset()
    signal typeIt()
    signal nudged(real gain)
    readonly property bool measured: !!meter && meter.peak !== undefined && meter.peak !== null
    readonly property bool held: meterBar.holdDb > F.FLOOR
    readonly property var shown: live ? (held ? meterBar.holdDb : null) : (measured ? meter.peak : null)
    implicitWidth: scale.width + fader.width + meterBar.width + 2 * Theme.grid
    Text {   // the held peak while playing ("−∞": silent), else the render's peak ("—" until a render has measured it)
        id: peakText
        anchors.horizontalCenter: meterBar.horizontalCenter; anchors.top: parent.top
        text: lv.shown !== null ? F.num(lv.shown, 1) : lv.live ? "−∞" : "—"
        color: lv.shown !== null ? Theme[F.levelTone(lv.shown)] : Theme.fg3
        font.family: uiFont; font.pixelSize: Theme.label; font.features: { "tnum": 1 }
    }
    MixScale { id: scale; anchors { left: parent.left; top: fader.top; bottom: fader.bottom } inset: 7 }
    MixFader {
        id: fader
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
        tip: lv.live ? "Level now: the bar is the average (RMS), the thin bar and the mark the peak"
             : lv.measured ? "Highest level in the last render: " + F.num(lv.meter.peak, 1) + " dB"
                           + (lv.meter.lufs !== null && lv.meter.lufs !== undefined ? ", loudness " + F.num(lv.meter.lufs, 1) + " LUFS" : "")
                           + ". Play to see the level move"
             : "Not measured yet: render to see the level"
    }
}
