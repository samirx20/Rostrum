import QtQuick
import RostrumKit

// Vertical grid lines behind blocks: bars clear, beats faint (only when far enough apart to read).
// `ruler` gives the mapping (a BarRuler of the same width).
Item {
    id: g
    property var ruler
    clip: true
    Repeater {
        model: Math.floor(g.ruler.length / backend.song.spb + 1e-6) + 1
        delegate: Rectangle {
            required property int index
            readonly property bool bar: index % backend.song.beatsPerBar === 0
            visible: (bar || backend.song.spb * g.ruler.perSec >= 14) && g.ruler.visibleX(x)
            x: Math.round(g.ruler.xOf(index * backend.song.spb)); width: 1; height: g.height
            color: bar ? Theme.border : Theme.panel
        }
    }
}
