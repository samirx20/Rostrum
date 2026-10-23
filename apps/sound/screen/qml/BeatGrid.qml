import QtQuick
import RostrumKit

// Vertical grid lines behind blocks: bars clear, beats faint (only when far enough apart to read).
// `ruler` gives the mapping (a BarRuler of the same width).
// One painted surface, not an item per beat: a song's beats are many (a 6-minute song has ~800, and every row has
// a grid), so items per beat grew with rows x beats and every read of `backend.song` copied the whole map. The grid
// reads the song once per change and paints only the beats that are on screen.
Item {
    id: g
    property var ruler
    clip: true
    readonly property var song: backend.song        // one read per change (each read of the property copies the map)
    readonly property real from: ruler.start        // the stretch on screen: the lines are painted from these
    readonly property real perSec: ruler.perSec
    Canvas {
        id: c
        anchors.fill: parent
        onWidthChanged: requestPaint(); onHeightChanged: requestPaint()
        Connections { target: g; function onSongChanged() { c.requestPaint() } function onFromChanged() { c.requestPaint() }
                      function onPerSecChanged() { c.requestPaint() } }
        onPaint: {
            var ctx = getContext("2d"); ctx.reset()
            var b = g.song.beats, bl = g.song.bars, ps = g.perSec, t0 = g.from - 2 / ps, t1 = g.from + (width + 2) / ps
            function first(a) { var lo = 0, hi = a.length
                while (lo < hi) { var m = (lo + hi) >> 1; if (a[m] < t0) lo = m + 1; else hi = m }
                return lo }                                                                        // first one on screen
            var bars = [], beats = []
            for (var j0 = first(bl); j0 < bl.length && bl[j0] <= t1; j0++) bars.push(Math.round((bl[j0] - g.from) * ps))
            for (var i = first(b); i < b.length && b[i] <= t1; i++) {
                var gap = i + 1 < b.length ? b[i + 1] - b[i] : g.song.spb
                if (gap * ps >= 14) beats.push(Math.round((b[i] - g.from) * ps))   // (a bar line paints over its beat)
            }
            ctx.fillStyle = Theme.panel
            for (var j = 0; j < beats.length; j++) ctx.fillRect(beats[j], 0, 1, height)
            ctx.fillStyle = Theme.border
            for (var k = 0; k < bars.length; k++) ctx.fillRect(bars[k], 0, 1, height)
        }
    }
}
