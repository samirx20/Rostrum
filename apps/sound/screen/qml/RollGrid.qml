import QtQuick
import RostrumKit

// The piano roll's drawing (clicks are PianoRoll's): rows (one per key, darker for black keys, or one per
// drum), their names at the left, the beat grid, and the track's notes, hits or clips. rowAt(y) is the one
// mapping from height to a key (MIDI number), a drum row, or 0 for clips.
Item {
    id: g
    property var roll
    property var ruler
    property int keysWidth: 52
    property real viewHeight: 400
    readonly property bool notes: roll.kind === "notes"
    readonly property int count: notes ? roll.hi - roll.lo + 1 : roll.kind === "drums" ? Math.max(1, roll.drums.length) : 1
    readonly property real rowH: notes ? Math.max(12, viewHeight / count)
                               : roll.kind === "drums" ? Math.min(40, viewHeight / count) : viewHeight
    function rowAt(y) { var i = Math.floor(y / rowH); return notes ? roll.hi - i : roll.kind === "drums" ? i : 0 }
    // The row names follow the key in force at the view's left edge: scrolling past a key change renames the keys.
    readonly property var rowNames: {
        var list = roll.rowNames, at = ruler.start + 1e-6, hit = list.length ? list[0].names : []
        for (var i = 0; i < list.length; i++) if (list[i].t <= at) hit = list[i].names
        return hit
    }
    function black(k) { return [1, 3, 6, 8, 10].indexOf(k % 12) >= 0 }
    height: count * rowH

    Repeater {   // rows and their names
        model: g.roll.kind === "audio" ? 0 : g.count
        delegate: Item {
            required property int index
            readonly property int key: g.roll.hi - index
            y: index * g.rowH; width: g.width; height: g.rowH
            Rectangle { x: g.keysWidth; width: parent.width - x; height: parent.height
                        color: g.notes && g.black(parent.key) ? Theme.app : "transparent" }
            Rectangle { x: g.keysWidth; width: parent.width - x; height: 1; y: parent.height - 1
                        visible: g.notes ? parent.key % 12 === 0 : true; color: Theme.border }
            Rectangle { width: g.keysWidth - 6; height: parent.height - 1; x: 0
                        color: g.notes && g.black(parent.key) ? Theme.app : Theme.panel }
            Text {
                visible: g.notes ? parent.key % 12 === 0 || g.rowH >= 16 && !g.black(parent.key) : true
                x: Theme.gap; anchors.verticalCenter: parent.verticalCenter
                text: g.notes ? g.rowNames[parent.index] : g.roll.drums[parent.index] || ""
                color: g.notes && parent.key % 12 !== 0 ? Theme.fg4 : Theme.fg3
                font.family: uiFont; font.pixelSize: Theme.label - (g.notes ? 1 : 0); font.features: { "tnum": 1 }
            }
        }
    }
    BeatGrid { x: g.keysWidth; width: g.width - x; height: g.height; ruler: g.ruler; opacity: 0.8 }

    Item {   // the plot: zoomed in, what is out of view is cut at the keys' edge
        x: g.keysWidth; width: g.width - x; height: g.height; clip: true
        Repeater {   // notes (a chord: one bar per key), hits, clips
            model: g.roll.blocks
            delegate: Item {
                id: b
                required property var modelData
                readonly property bool on: modelData.id === backend.selected
                x: Math.round(g.ruler.xOf(modelData.t)); width: g.width; height: g.height
                Repeater {
                    model: b.modelData.type === "note" ? b.modelData.keys : []
                    delegate: Rectangle {
                        required property int modelData
                        y: (g.roll.hi - modelData) * g.rowH + 1; height: g.rowH - 2
                        width: Math.max(4, g.ruler.wOf(b.modelData.dur) - 1); radius: 3
                        color: b.on ? Theme.accent : g.roll.hue
                        border.width: b.on ? 1 : 0; border.color: Theme.fg
                        Text { visible: parent.width >= implicitWidth + 5 && g.rowH >= 14   // whenever the name fits the bar
                               x: 3; anchors.verticalCenter: parent.verticalCenter
                               text: b.modelData.names[b.modelData.keys.indexOf(parent.modelData)]; color: Theme.app; font.family: uiFont
                               font.pixelSize: Theme.label - 1; font.weight: Font.DemiBold }
                    }
                }
                Rectangle {   // a hit: a diamond on its drum's row
                    visible: b.modelData.type === "hit"
                    readonly property real s: Math.min(12, g.rowH * 0.5)
                    x: -s / 2; y: g.roll.drums.indexOf(b.modelData.drum) * g.rowH + (g.rowH - s) / 2
                    width: s; height: s; rotation: 45; radius: 2
                    color: b.on ? Theme.accent : g.roll.hue; opacity: b.on ? 1 : 0.5 + 0.5 * (b.modelData.vel || 0)
                    border.width: b.on ? 1 : 0; border.color: Theme.fg
                }
                Rectangle {   // a clip: its waveform
                    visible: b.modelData.type === "clip" || b.modelData.type === "line"
                    y: g.height * 0.2; height: g.height * 0.6; width: Math.max(4, g.ruler.wOf(b.modelData.dur))
                    radius: 4; color: "transparent"; border.width: 1; border.color: b.on ? Theme.accent : g.roll.hue
                    Text { x: 8; y: 6; width: parent.width - 16; elide: Text.ElideRight   // stays inside its block
                           text: b.modelData.label; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.label }
                    Row {
                        anchors.fill: parent; anchors.margins: 4; anchors.topMargin: 24
                        Repeater {
                            model: b.modelData.peaks || []
                            delegate: Item {
                                required property real modelData
                                width: parent.width / Math.max(1, b.modelData.peaks.length); height: parent.height
                                Rectangle { anchors.centerIn: parent; width: Math.max(1, parent.width - 2); radius: 1
                                            height: Math.max(1, parent.height * modelData)
                                            color: b.on ? Theme.accent : g.roll.hue; opacity: 0.85 }
                            }
                        }
                    }
                }
            }
        }
    }
}
