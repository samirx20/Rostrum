import QtQuick
import QtQuick.Layouts
import RostrumKit
import "MixFormat.js" as F

// The master's loudness, from the render that plays: the short-term loudness at the playhead with its curve (and the
// target as a dashed line), the true peak (so far while playing, else the whole mix) and, while playing, the loudness
// so far. The whole mix's loudness is not said here: it is the top bar's chip. Numbers are green inside the target,
// amber outside it. Choosing the target is in the Deliver dialog.
ColumnLayout {
    id: l
    readonly property var meter: mixer.loudness
    readonly property var target: meter.target
    readonly property var info: mixer.master
    readonly property bool measured: !!info.meter && info.meter.lufs !== undefined
    spacing: Theme.gap

    Text { visible: !l.measured; Layout.fillWidth: true; Layout.fillHeight: true; verticalAlignment: Text.AlignTop; wrapMode: Text.WordWrap
           text: "Measuring the loudness…"; color: Theme.fg4; font.family: uiFont; font.pixelSize: Theme.body }
    ColumnLayout {   // the curve takes the height that is left: no dead space in the strip
        visible: l.measured
        Layout.fillWidth: true; Layout.fillHeight: true; spacing: 2
        Text { visible: backend.playing; text: "Loudness right now"; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label }
        Row {
            visible: backend.playing
            spacing: Theme.grid + 2
            HoverHandler { id: nowHover }
            HoverTip { y: parent.height + 2; text: "Short-term loudness (LUFS-S): how loud the last 3 seconds were"; hovered: nowHover.hovered }
            Text { id: big; text: F.num(l.meter.shortTerm, 1); color: Theme.fg; font.family: uiFont; font.pixelSize: 28
                   font.weight: Font.DemiBold; font.features: { "tnum": 1 } }
            Text { anchors.baseline: big.baseline; text: "LUFS"; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.body }
        }
        LoudnessCurve {
            visible: l.height >= 170         // a short strip: the curve folds away, the numbers stay
            Layout.fillWidth: true; Layout.fillHeight: true; Layout.minimumHeight: 64; Layout.topMargin: Theme.grid
            values: l.meter.curve; hop: l.meter.axis.hop; window: l.meter.axis.window; seconds: l.meter.axis.seconds
            target: l.target.shown && l.target.lufs != null ? l.target.lufs : null
            now: backend.time
        }
        RowLayout {
            Layout.fillWidth: true; Layout.topMargin: Theme.grid; spacing: Theme.gap
            Repeater {
                model: [{ what: backend.playing ? "Loudest peak so far" : "Loudest peak", unit: "dBTP",
                          tip: "True peak (dBTP): the highest level the sound reaches between samples",
                          v: backend.playing && l.meter.peakNow !== null ? l.meter.peakNow : l.info.meter.truePeak, ok: (v) => v <= l.target.peak }].concat(
                        // the whole mix's loudness is the top bar's chip; only while playing is "so far" a different number
                        backend.playing && l.meter.integratedNow != null
                            ? [{ what: "Loudness so far", unit: "LUFS", tip: "Integrated loudness (LUFS) from the start up to now", v: l.meter.integratedNow, ok: (v) => Math.abs(v - l.target.lufs) <= 1 }] : [])
                delegate: Column {
                    required property var modelData
                    Layout.fillWidth: true; Layout.preferredWidth: 1
                    HoverHandler { id: numHover }
                    HoverTip { text: modelData.tip; hovered: numHover.hovered }
                    Text { text: modelData.what; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label }
                    Row {
                        spacing: Theme.grid
                        Text { id: num; text: F.num(modelData.v, 1)
                               color: !l.target.shown || l.target.lufs == null ? Theme.fg : modelData.ok(modelData.v) ? Theme.ok : Theme.warn; font.family: uiFont; font.pixelSize: 18
                               font.weight: Font.DemiBold; font.features: { "tnum": 1 } }
                        Text { anchors.baseline: num.baseline; text: modelData.unit; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label }
                    }
                }
            }
        }
    }
}
