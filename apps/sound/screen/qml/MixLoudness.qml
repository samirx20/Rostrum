import QtQuick
import QtQuick.Layouts
import RostrumKit
import "MixFormat.js" as F

// The master's loudness, from the render that plays: the normalize / target rows (by valid_when), the delivery target
// (only while normalize is on), the short-term loudness at the playhead with its curve, the true peak (so far while
// playing, else the whole mix), the integrated loudness of the whole mix, and the pass / miss line against the target.
ColumnLayout {
    id: l
    property var proxy                                  // what an InspectorRow calls on its "bridge": the master
    readonly property var meter: mixer.loudness
    readonly property var target: meter.target
    readonly property var info: mixer.master
    readonly property bool measured: !!info.meter && info.meter.lufs !== undefined
    spacing: Theme.gap

    Column {
        Layout.fillWidth: true
        Repeater { model: mixer.masterRows; delegate: InspectorRow { bridge: l.proxy } }
    }
    MixPick {   // where it is going: one pick sets the target's loudness and true peak together
        visible: l.target.shown
        Layout.fillWidth: true; Layout.preferredHeight: 22
        popupWidth: 200
        text: "Deliver to: " + l.target.label
        choices: (l.target.choices || []).map(c => ({ id: c.id, label: c.label + "   " + c.detail }))
        onPicked: (id) => l.meter.choose(id)
    }
    Item { Layout.fillHeight: true }
    Text { visible: !l.measured; Layout.fillWidth: true; wrapMode: Text.WordWrap
           text: "Render to measure loudness"; color: Theme.fg4; font.family: uiFont; font.pixelSize: Theme.body }
    ColumnLayout {
        visible: l.measured
        Layout.fillWidth: true; spacing: 2
        Text { text: "Short-term loudness"; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label }
        Row {
            spacing: Theme.grid + 2
            Text { id: big; text: F.num(l.meter.shortTerm, 1); color: Theme.fg; font.family: uiFont; font.pixelSize: 28
                   font.weight: Font.DemiBold; font.features: { "tnum": 1 } }
            Text { anchors.baseline: big.baseline; text: "LUFS-S"; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.body }
        }
        LoudnessCurve {
            Layout.fillWidth: true; Layout.preferredHeight: 64
            values: l.meter.curve; hop: l.meter.axis.hop; window: l.meter.axis.window; seconds: l.meter.axis.seconds
            target: l.target.shown && l.target.lufs != null ? l.target.lufs : null
            now: backend.time
        }
        RowLayout {
            Layout.fillWidth: true; Layout.topMargin: Theme.grid; spacing: Theme.gap
            Repeater {
                model: [{ what: backend.playing ? "True peak so far" : "True peak", unit: "dBTP",
                          v: backend.playing && l.meter.peakNow !== null ? l.meter.peakNow : l.info.meter.truePeak },
                        backend.playing && l.meter.integratedNow != null
                            ? { what: "Integrated so far", unit: "LUFS", v: l.meter.integratedNow }
                            : { what: "Integrated (whole mix)", unit: "LUFS", v: l.info.meter.lufs }]
                delegate: Column {
                    required property var modelData
                    Layout.fillWidth: true; Layout.preferredWidth: 1
                    Text { text: modelData.what; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label }
                    Row {
                        spacing: Theme.grid
                        Text { id: num; text: F.num(modelData.v, 1); color: Theme.fg; font.family: uiFont; font.pixelSize: 18
                               font.weight: Font.DemiBold; font.features: { "tnum": 1 } }
                        Text { anchors.baseline: num.baseline; text: modelData.unit; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label }
                    }
                }
            }
        }
        Text {   // pass / miss against the master's own target (only while there is one)
            visible: l.target.shown && !!l.target.verdict.text
            Layout.fillWidth: true; Layout.topMargin: Theme.grid; wrapMode: Text.WordWrap
            text: l.target.verdict.text || ""
            color: l.target.verdict.ok ? Theme.ok : Theme.warn
            font.family: uiFont; font.pixelSize: Theme.body
        }
    }
}
