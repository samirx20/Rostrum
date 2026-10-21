import QtQuick
import QtQuick.Layouts
import RostrumKit
import "MixFormat.js" as F

// The master strip: name, its insert chain, the fader, the loudness rows (the target only while normalize is on),
// and what the last render measured, in big numbers.
Rectangle {
    id: m
    readonly property var info: mixer.master          // id, name, volume, effects, meter
    readonly property bool measured: !!info.meter && info.meter.lufs !== undefined
    width: 260
    color: Theme.app
    radius: Theme.radiusPanel
    border.width: backend.selected === "master" ? 1 : 0; border.color: Theme.accent

    function pick() { if (backend.selected !== "master") backend.select("master") }
    QtObject {   // what an InspectorRow calls on its "bridge": the master, whatever is selected
        id: proxy
        readonly property bool moreOpen: false
        function setValue(p, v) { m.pick(); return backend.setValue(p, v) }
        function beginScrub(p) { m.pick(); backend.beginScrub(p) }
        function scrub(p, v) { m.pick(); backend.scrub(p, v) }
        function endScrub() { backend.endScrub() }
        function toggleMore() {}
    }

    ColumnLayout {
        anchors.fill: parent; anchors.margins: Theme.gap + 2
        spacing: Theme.gap
        Text {
            Layout.fillWidth: true; Layout.preferredHeight: 22
            text: "Master"; color: Theme.fg; verticalAlignment: Text.AlignVCenter
            font.family: uiFont; font.pixelSize: Theme.title; font.weight: Font.DemiBold
            MouseArea { anchors.fill: parent; onPressed: m.pick() }
        }
        MixChain { Layout.fillWidth: true; Layout.preferredHeight: 84; chips: m.info.effects; ownerId: "master" }
        RowLayout {
            Layout.fillWidth: true; Layout.fillHeight: true; spacing: Theme.pad
            ColumnLayout {  // fader, meter, level
                Layout.fillHeight: true; spacing: Theme.gap
                RowLayout {
                    Layout.fillHeight: true; spacing: Theme.gap
                    MixFader {
                        Layout.fillHeight: true; Layout.preferredWidth: 28
                        gain: m.info.volume
                        onScrubStarted: { m.pick(); backend.beginScrub("volume") }
                        onScrubbed: (g) => backend.scrub("volume", g)
                        onScrubEnded: backend.endScrub()
                    }
                    MixMeter { Layout.fillHeight: true; Layout.topMargin: 7; Layout.bottomMargin: 7; peak: m.info.meter.peak }
                }
                Text { Layout.alignment: Qt.AlignHCenter; text: F.faderText(m.info.volume); color: Theme.fg
                       font.family: uiFont; font.pixelSize: Theme.body; font.features: { "tnum": 1 } }
            }
            ColumnLayout {  // loudness
                Layout.fillWidth: true; Layout.fillHeight: true; spacing: 0
                Column {
                    Layout.fillWidth: true
                    Repeater {
                        model: mixer.masterRows
                        delegate: InspectorRow { bridge: proxy }
                    }
                }
                Item { Layout.fillHeight: true }
                Text { visible: !m.measured; Layout.fillWidth: true; wrapMode: Text.WordWrap
                       text: "Render to measure loudness"; color: Theme.fg4; font.family: uiFont; font.pixelSize: Theme.body }
                Repeater {
                    model: m.measured ? [{ v: m.info.meter.lufs, unit: "LUFS", what: "Integrated loudness" },
                                         { v: m.info.meter.truePeak, unit: "dBTP", what: "True peak" }] : []
                    delegate: Column {
                        required property var modelData
                        Layout.fillWidth: true; Layout.bottomMargin: Theme.gap
                        Text { text: modelData.what; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label }
                        Row {
                            spacing: Theme.grid + 2
                            Text { id: big; text: F.num(modelData.v, 1); color: Theme.fg; font.family: uiFont; font.pixelSize: 28
                                   font.weight: Font.DemiBold; font.features: { "tnum": 1 } }
                            Text { anchors.baseline: big.baseline; text: modelData.unit; color: Theme.fg3
                                   font.family: uiFont; font.pixelSize: Theme.body }
                        }
                    }
                }
            }
        }
    }
}
