import QtQuick
import QtQuick.Layouts
import RostrumKit
import "MixFormat.js" as F

// The master strip: name, its insert chain, the fader, the loudness (MixLoudness: target only while normalize is on,
// live short-term loudness and true peak at the playhead, pass / miss) and "Render mix and stems" (MixExport).
Rectangle {
    id: m
    readonly property var info: mixer.master          // id, name, volume, effects, meter
    readonly property real minBody: Math.max(140, loud.implicitHeight)   // fader travel, the loudness at its smallest curve
    readonly property real need: 22 + chain.height + minBody + 2 * Theme.gap     // the least it can do with (MixPage)
                                 + export_.height + 2 * (Theme.gap + 2) + Theme.gap   // the height it can't do without (MixPage)
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

    Flickable {      // a short window: the card scrolls instead of laying its parts over each other
        id: flick
        anchors { left: parent.left; right: parent.right; top: parent.top; bottom: export_.top
                  margins: Theme.gap + 2; bottomMargin: Theme.gap }
        contentHeight: col.height; clip: true; boundsBehavior: Flickable.StopAtBounds
        interactive: contentHeight > height
    ColumnLayout {
        id: col
        width: flick.width; height: Math.max(flick.height, 22 + chain.height + m.minBody + 2 * Theme.gap)   // fits, down to its least
        spacing: Theme.gap
        Text {
            Layout.fillWidth: true; Layout.preferredHeight: 22
            text: "Master"; color: Theme.fg; verticalAlignment: Text.AlignVCenter
            font.family: uiFont; font.pixelSize: Theme.title; font.weight: Font.DemiBold
            MouseArea { anchors.fill: parent; onPressed: m.pick() }
        }
        MixChain { id: chain; Layout.fillWidth: true; Layout.preferredHeight: contentHeight;   // as tall as its chips, no reserve
                   chips: m.info.effects; ownerId: "master" }
        RowLayout {
            Layout.fillWidth: true; Layout.fillHeight: true; spacing: Theme.pad
            Layout.minimumHeight: m.minBody
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
            MixLoudness { id: loud; Layout.fillWidth: true; Layout.fillHeight: true; proxy: masterBridge }
        }
    }
    }
    MixExport {      // Render always in sight: the fader and loudness above give way first
        id: export_
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom; margins: Theme.gap + 2 }
    }
}
