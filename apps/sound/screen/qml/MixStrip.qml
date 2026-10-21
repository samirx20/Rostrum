import QtQuick
import QtQuick.Layouts
import RostrumKit
import "MixFormat.js" as F

// One track's strip: name, effect chain, pan, mute / solo, fader with its meter, and the numbers.
// Editing selects the track first, so the inspector shows it and the edit is one change on it.
Rectangle {
    id: s
    required property var model          // roles: id, name, volume, pan, mute, solo, effects, meter
    readonly property bool selected: backend.selected === model.id
    readonly property bool measured: !!model.meter && model.meter.peak !== undefined
    width: 124
    color: Theme.app
    radius: Theme.radiusPanel
    border.width: selected ? 1 : 0; border.color: Theme.accent

    function pick() { if (backend.selected !== model.id) backend.select(model.id) }

    ColumnLayout {
        anchors.fill: parent; anchors.margins: Theme.gap + 2
        spacing: Theme.gap
        Text {
            Layout.fillWidth: true; Layout.preferredHeight: 22
            text: s.model.name; elide: Text.ElideRight; color: Theme.fg; verticalAlignment: Text.AlignVCenter
            font.family: uiFont; font.pixelSize: Theme.title; font.weight: Font.DemiBold
            MouseArea { anchors.fill: parent; onPressed: s.pick() }
        }
        MixChain { Layout.fillWidth: true; Layout.preferredHeight: 84; chips: s.model.effects; ownerId: s.model.id }
        ColumnLayout {  // pan
            Layout.fillWidth: true; spacing: 0
            RowLayout {
                Layout.fillWidth: true
                Text { text: "Pan"; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label }
                Item { Layout.fillWidth: true }
                Text { text: F.panText(s.model.pan); color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.label
                       font.features: { "tnum": 1 } }
            }
            Slider {
                Layout.fillWidth: true; implicitWidth: 10
                from: -1; to: 1; step: 0.01; value: s.model.pan
                onScrubStarted: { s.pick(); backend.beginScrub("pan") }
                onScrubbed: (v) => backend.scrub("pan", v)
                onScrubEnded: backend.endScrub()
            }
        }
        RowLayout {
            Layout.fillWidth: true; spacing: Theme.grid
            MixSwitch { Layout.fillWidth: true; text: "M"; on: s.model.mute; tint: Theme.warn
                        onToggled: (v) => { s.pick(); backend.setValue("mute", v) } }
            MixSwitch { Layout.fillWidth: true; text: "S"; on: s.model.solo; tint: Theme.accent
                        onToggled: (v) => { s.pick(); backend.setValue("solo", v) } }
        }
        RowLayout {  // fader and meter
            Layout.fillWidth: true; Layout.fillHeight: true; spacing: Theme.gap
            Item { Layout.fillWidth: true }
            MixFader {
                Layout.fillHeight: true; Layout.preferredWidth: 28
                gain: s.model.volume
                onScrubStarted: { s.pick(); backend.beginScrub("volume") }
                onScrubbed: (g) => backend.scrub("volume", g)
                onScrubEnded: backend.endScrub()
            }
            MixMeter { Layout.fillHeight: true; Layout.topMargin: 7; Layout.bottomMargin: 7; peak: s.model.meter.peak }
            Item { Layout.fillWidth: true }
        }
        Text {
            Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter
            text: F.faderText(s.model.volume); color: Theme.fg
            font.family: uiFont; font.pixelSize: Theme.body; font.features: { "tnum": 1 }
        }
        Text {   // measured by the last render; absent until there is one
            Layout.fillWidth: true; Layout.preferredHeight: 28; horizontalAlignment: Text.AlignHCenter
            visible: s.measured
            text: F.num(s.model.meter.peak, 1) + " pk\n" + F.num(s.model.meter.lufs, 1) + " LUFS"
            color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label; font.features: { "tnum": 1 }
        }
    }
}
