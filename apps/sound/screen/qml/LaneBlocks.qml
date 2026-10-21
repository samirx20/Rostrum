import QtQuick
import RostrumKit

// One track's things in an arrangement row, drawn only (clicks are the Timeline's): notes as thin bars placed
// by pitch (a chord: one per key), drum hits as ticks placed by drum, recorded clips as blocks with their
// waveform. The selected one is drawn in the accent colour. `ruler` gives the time mapping.
Item {
    id: lane
    property var track
    property var ruler
    readonly property int pad: 3
    readonly property real mark: Math.max(2, Math.min(5, height / 9))     // a note bar's thickness
    opacity: track.mute ? 0.45 : 1

    Repeater {
        model: lane.track.blocks
        delegate: Item {
            id: b
            required property var modelData
            readonly property bool on: modelData.id === backend.selected
            readonly property bool isClip: modelData.type === "clip" || modelData.type === "line"
            readonly property real barH: modelData.type === "hit" ? lane.mark * 1.8 : lane.mark
            x: Math.round(lane.ruler.xOf(modelData.t))
            y: lane.pad; height: lane.height - 2 * lane.pad
            width: modelData.type === "hit" ? (on ? 3 : 2) : Math.max(2, lane.ruler.wOf(modelData.dur) - 1)
            z: on ? 2 : isClip ? 0 : 1

            Repeater {   // notes and hits: a bar per lane
                model: b.isClip ? [] : b.modelData.lanes
                delegate: Rectangle {
                    required property real modelData
                    y: modelData * (b.height - b.barH); width: b.width; height: b.barH; radius: 1
                    color: b.on ? Theme.accent : lane.track.hue
                }
            }
            Rectangle {   // a clip: a soft fill and an edge
                visible: b.isClip; anchors.fill: parent; radius: 4
                color: b.on ? Theme.accent : lane.track.hue; opacity: b.on ? 0.3 : 0.18
            }
            Rectangle {
                visible: b.isClip; anchors.fill: parent; radius: 4; color: "transparent"
                border.width: 1; border.color: b.on ? Theme.accent : lane.track.hue
            }
            Row {         // a clip's waveform: peaks as bars around its middle
                visible: b.isClip
                anchors.fill: parent; anchors.margins: 2; anchors.topMargin: label.visible ? 14 : 2
                Repeater {
                    model: b.isClip ? b.modelData.peaks : []
                    delegate: Item {
                        required property real modelData
                        width: parent.width / Math.max(1, b.modelData.peaks.length); height: parent.height
                        Rectangle { anchors.centerIn: parent; width: Math.max(1, parent.width - 1); radius: 0.5
                                    height: Math.max(1, parent.height * modelData)
                                    color: b.on ? Theme.accent : lane.track.hue; opacity: 0.85 }
                    }
                }
            }
            Text {
                id: label
                visible: b.isClip && lane.height >= 30
                x: 6; y: 2; width: parent.width - 10; elide: Text.ElideRight
                text: b.modelData.label; color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.label - 1
            }
        }
    }
}
