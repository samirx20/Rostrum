import QtQuick
import RostrumKit

// Show beats (the Sound row's menu, backend.soundtrack.beats: the song's tempo grid from Sound): a faint line per beat and a
// stronger one per bar across the rows, the bar's number at the top of the ruler, left of its line. Lines closer than
// a few px are left out (zoomed out, the bars stay); a number that would touch the next is left out too.
Item {
    id: lines
    property Item ruler
    property real bottomY: 0
    readonly property var beats: backend.soundtrack.beats
    readonly property real beatPx: beats.length > 1 ? ruler.xOf(beats[1].t) - ruler.xOf(beats[0].t) : 0
    readonly property real barPx: beatPx * Math.max(1, beats.findIndex((b, i) => i > 0 && b.bar > 0))
    readonly property int numberEvery: Math.max(1, Math.ceil(22 / Math.max(1, barPx)))
    Repeater {
        model: lines.beats
        delegate: Item {
            required property var modelData
            readonly property bool bar: modelData.bar > 0
            visible: (bar || lines.beatPx >= 5) && modelData.t <= lines.ruler.duration + 1e-6
            x: lines.ruler.x + Math.round(lines.ruler.xOf(modelData.t)); y: lines.ruler.y
            Rectangle {
                y: parent.bar ? 0 : lines.ruler.height - 6
                width: 1; height: lines.bottomY - lines.ruler.y - y
                color: Theme.fg; opacity: parent.bar ? 0.22 : 0.08
            }
            Text {   // left of its line (a marker's flag hangs to the right of its own); bar 1 inside the ruler
                visible: parent.bar && (modelData.bar - 1) % lines.numberEvery === 0 && modelData.t < lines.ruler.duration - 1e-6
                         && !backend.markers.some(m => Math.abs(lines.ruler.xOf(m.at) - lines.ruler.xOf(modelData.t)) < width + 8)   // not against a marker
                x: modelData.t > 0 ? -width - 3 : 3; y: 1
                text: modelData.bar; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label
            }
        }
    }
}
