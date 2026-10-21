import QtQuick
import RostrumKit

// The playhead as text: bar.beat first, seconds after ("5.1  9.60 s"), digits all one width; then the sound's
// state when there is one to tell (rendering, no output here, a failed render: red).
Row {
    spacing: Theme.gap
    readonly property real spb: backend.song.spb
    readonly property int bpb: backend.song.beatsPerBar
    readonly property real beats: backend.time / spb + 1e-6
    Item { width: 2; height: 1 }
    Text { text: (Math.floor(parent.beats / parent.bpb) + 1) + "." + (Math.floor(parent.beats) % parent.bpb + 1)
           width: 36; color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body; font.features: { "tnum": 1 }
           anchors.verticalCenter: parent.verticalCenter }
    Text { text: backend.time.toFixed(2) + " s"; width: 52; color: Theme.fg3; font.family: uiFont
           font.pixelSize: Theme.label; font.features: { "tnum": 1 }; anchors.verticalCenter: parent.verticalCenter }
    Text { visible: text !== ""; text: backend.soundState; anchors.verticalCenter: parent.verticalCenter
           color: /^Render failed/.test(text) ? Theme.danger : Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label }
}
