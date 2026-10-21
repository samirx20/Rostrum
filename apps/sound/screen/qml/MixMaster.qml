import QtQuick
import QtQuick.Layouts
import RostrumKit
import "MixFormat.js" as F

// The master strip: name, its insert chain, the fader, the loudness (MixLoudness: target only while normalize is on,
// live short-term loudness and true peak at the playhead, pass / miss) and "Render mix and stems" (MixExport).
Rectangle {
    id: m
    readonly property var info: mixer.master          // id, name, volume, effects, meter
    width: 330
    color: Theme.app
    radius: Theme.radiusPanel
    border.width: backend.selected === "master" ? 1 : 0; border.color: Theme.accent

    function pick() { if (backend.selected !== "master") backend.select("master") }
    QtObject {   // what an InspectorRow calls on its "bridge": the master, whatever is selected
        id: masterBridge
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
        MixChain { Layout.fillWidth: true; Layout.preferredHeight: 56; chips: m.info.effects; ownerId: "master" }
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
            MixLoudness { Layout.fillWidth: true; Layout.fillHeight: true; proxy: masterBridge }
        }
        MixExport { Layout.fillWidth: true }
    }
}
