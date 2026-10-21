import QtQuick
import RostrumKit

// Vertical grid lines behind blocks: bars clear, beats faint (only when far enough apart to read).
// `ruler` gives the mapping (a BarRuler of the same width).
Item {
    id: g
    property var ruler
    clip: true
    Repeater {
        model: backend.song.beats            // every beat's time (the tempo map)
        delegate: Rectangle {
            required property int index
            required property real modelData
            readonly property var beats: backend.song.beats
            readonly property bool bar: index % backend.song.beatsPerBar === 0
            readonly property real gap: index + 1 < beats.length ? beats[index + 1] - modelData : backend.song.spb
            visible: (bar || gap * g.ruler.perSec >= 14) && g.ruler.visibleX(x)
            x: Math.round(g.ruler.xOf(modelData)); width: 1; height: g.height
            color: bar ? Theme.border : Theme.panel
        }
    }
}
