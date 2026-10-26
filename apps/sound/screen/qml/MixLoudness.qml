import QtQuick
import QtQuick.Layouts
import RostrumKit
import "MixFormat.js" as F

// The loudness panel beside the Master (mockup s51 #2), from the render that plays: the target in the title, three big
// numbers (integrated: the whole mix, or so far while playing; short-term at the playhead; true peak: the whole mix,
// or so far while playing), then the short-term curve over the song with the target as a dashed line and the
// playhead. Integrated and peak are green inside the target, amber outside it. Choosing the target is the Deliver dialog.
Rectangle {
    id: l
    readonly property var meter: mixer.loudness
    readonly property var target: meter.target
    readonly property var info: mixer.master
    readonly property bool measured: !!info.meter && info.meter.lufs !== undefined
    readonly property bool aimed: !!target.shown && target.lufs != null      // a delivery target applies (Normalize on)
    readonly property real goal: aimed ? target.lufs : meter.goal             // what the top bar's chip measures against too
    readonly property bool playing: backend.playing
    readonly property bool wide: width >= 400                                 // room for the big numbers
    color: Theme.app; radius: Theme.radiusPanel; clip: true
    // short-term at the playhead is empty before the first 3 s window ends and while stopped at the start: show the last
    // value there was, dimmed (`stale`); a song that never had one hides the number
    property var lastShort: null
    readonly property bool stale: meter.shortTerm == null
    Connections { target: l.meter; function onNowChanged() { if (l.meter.shortTerm != null) l.lastShort = l.meter.shortTerm } }

    function targetText() {
        return "target " + F.num(l.goal, 0) + " LUFS" + (l.aimed ? " (" + l.target.label + ")" : "")
    }
    // the three numbers: what, its value, its unit, the plain-words tip, and whether it is inside the target (null: no colour)
    readonly property var numbers: [
        { what: l.playing ? "So far" : "Whole song", unit: "LUFS",
          tip: l.playing ? "How loud the song has been from the start up to now (LUFS, as streaming sites measure it)" : "How loud the whole song is (LUFS, as streaming sites and broadcasters measure it)",
          v: l.playing && l.meter.integratedNow != null ? l.meter.integratedNow : l.info.meter.lufs,
          ok: (v) => Math.abs(v - l.goal) <= 1 },
        { what: "Now", unit: "LUFS", tip: "How loud the 3 seconds before the playhead are (LUFS)",
          v: l.stale ? l.lastShort : l.meter.shortTerm, stale: l.stale, ok: (v) => null },
        { what: l.playing ? "Loudest so far" : "Loudest peak", unit: "dBTP",
          tip: "The highest level the sound reaches, between samples too (dBTP)",
          v: l.playing && l.meter.peakNow != null ? l.meter.peakNow : l.info.meter.truePeak,
          ok: (v) => !l.target.shown || v <= l.target.peak ? null : false } ]   // plain under the ceiling, amber over it

    ColumnLayout {
        anchors { fill: parent; margins: Theme.pad }
        spacing: Theme.gap
        Flow {   // the title, with the target it is measured against (on a line of its own when the panel is narrow: never cut)
            id: titleFlow
            Layout.fillWidth: true; Layout.preferredHeight: implicitHeight; spacing: Theme.grid + 2
            Text { height: 22; verticalAlignment: Text.AlignVCenter; text: "Loudness"; color: Theme.fg
                   font.family: uiFont; font.pixelSize: Theme.title; font.weight: Font.DemiBold }
            Text { width: Math.min(implicitWidth, titleFlow.width); wrapMode: Text.WordWrap; topPadding: 3; text: l.targetText()
                   color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.title; font.features: { "tnum": 1 } }
        }
        Text { visible: !l.measured; Layout.fillWidth: true; Layout.fillHeight: true; verticalAlignment: Text.AlignTop; wrapMode: Text.WordWrap
               text: "Measuring the loudness…"; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.body }
        Flow {   // the three numbers, side by side at their own widths (smaller in a narrow panel; they wrap when narrower)
            visible: l.measured
            Layout.fillWidth: true; spacing: l.wide ? Theme.groupGap + Theme.gap : Theme.groupGap
            Repeater {
                model: l.numbers
                delegate: Item {   // an Item round the Column: the tip fills its parent, which a Column does not allow
                    id: num
                    required property var modelData
                    visible: modelData.what !== "Now" || modelData.v != null
                    readonly property var ok: modelData.v == null ? null : modelData.ok(modelData.v)
                    width: numCol.width; height: numCol.height
                    HoverHandler { id: numHover }
                    HoverTip { atY: num.height + 2; text: num.modelData.tip; hovered: numHover.hovered }
                    Column {
                        id: numCol
                        spacing: 2
                        Text { text: num.modelData.what; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label }
                        Row {
                            spacing: Theme.grid + 1
                            Text { id: big; text: F.num(num.modelData.v, 1); font.family: uiFont; font.pixelSize: l.wide ? 26 : 20
                                   color: num.modelData.v == null || num.modelData.stale ? Theme.fg3 : num.ok === null ? Theme.fg : num.ok ? Theme.ok : Theme.warn
                                   font.weight: Font.DemiBold; font.features: { "tnum": 1 } }
                            Text { anchors.baseline: big.baseline; visible: num.modelData.v != null; text: num.modelData.unit; color: Theme.fg3
                                   font.family: uiFont; font.pixelSize: Theme.label }
                        }
                    }
                }
            }
        }
        LoudnessCurve {   // fills the height that is left
            visible: l.measured
            Layout.fillWidth: true; Layout.fillHeight: true; Layout.topMargin: Theme.grid
            values: l.meter.curve; hop: l.meter.axis.hop; window: l.meter.axis.window; seconds: l.meter.axis.seconds
            target: l.goal
            now: backend.time
        }
    }
}
