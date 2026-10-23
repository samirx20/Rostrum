import QtQuick
import RostrumKit
import "MixFormat.js" as F

// A strip's level block, left to right: the dB scale, the fader, the meter with its peak number above it. The scale
// and the meter sit on the fader's own travel (inset by half the knob), so their marks line up with the knob.
Item {
    id: lv
    property real gain: 1
    property var meter: ({})            // {peak, lufs} from the last render, or {}: not measured
    signal scrubStarted()
    signal scrubbed(real gain)
    signal scrubEnded()
    readonly property bool measured: !!meter && meter.peak !== undefined && meter.peak !== null
    implicitWidth: scale.width + fader.width + meterBar.width + 2 * Theme.grid
    Text {   // the meter's peak in dBFS, "—" until a render has measured it
        id: peakText
        anchors.horizontalCenter: meterBar.horizontalCenter; anchors.top: parent.top
        text: lv.measured ? F.num(lv.meter.peak, 1) : "—"
        color: lv.measured ? Theme[F.levelTone(lv.meter.peak)] : Theme.fg3
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
    }
    MixMeter {
        id: meterBar
        anchors { left: fader.right; leftMargin: Theme.grid; top: fader.top; bottom: fader.bottom; topMargin: 7; bottomMargin: 7 }
        peak: lv.measured ? lv.meter.peak : null
        tip: lv.measured ? "Highest level in the last render: " + F.num(lv.meter.peak, 1) + " dB"
                           + (lv.meter.lufs !== null && lv.meter.lufs !== undefined ? ", loudness " + F.num(lv.meter.lufs, 1) + " LUFS" : "")
                         : "Not measured yet: render to see the level"
    }
}
