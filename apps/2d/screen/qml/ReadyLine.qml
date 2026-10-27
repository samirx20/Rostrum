import QtQuick
import RostrumKit

// The time ruler's ready line (PLAN D2, After Effects' cache line): a thin line along the ruler's bottom under the
// frames whose scrub picture is drawn ahead (backend.scrubAhead.ready, scrub_ahead.py): a scrub or a click there shows
// its picture at once. It fills out from the playhead while the canvas is idle; a change or a new view empties it.
Item {
    id: line
    property Item ruler
    readonly property var ready: backend.scrubAhead.ready
    readonly property real step: 1 / (backend.frameInfo.fps || 30)
    readonly property var runs: {           // [[from, to]] of frames next to each other, in seconds
        const out = []
        for (const t of ready) {
            const last = out.length ? out[out.length - 1] : null
            if (last && t - last[1] <= step * 1.5) last[1] = t
            else out.push([t, t])
        }
        return out
    }
    Repeater {
        model: line.runs
        delegate: Rectangle {
            required property var modelData
            x: line.ruler.x + Math.round(line.ruler.xOf(modelData[0]))
            width: Math.max(1, Math.round(line.ruler.xOf(modelData[1] + line.step) - line.ruler.xOf(modelData[0])))
            y: line.ruler.y + line.ruler.height - height
            height: 2
            color: Theme.ok; opacity: 0.8
        }
    }
}
