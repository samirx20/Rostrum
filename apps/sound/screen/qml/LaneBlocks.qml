import QtQuick
import RostrumKit

// One track's things in an arrangement row, drawn only (clicks are the Timeline's): notes as thin bars placed
// by pitch (a chord: one per key), drum hits as ticks placed by drum, recorded clips as blocks with their
// waveform. Every selected one is drawn in the accent colour (backend.picked). `ruler` gives the time mapping.
// One painted surface per row, not a few items per note: a song of 14,000 notes made over a hundred thousand
// items and over a gigabyte of screen memory. Only what is on screen is painted, and it is painted again only
// when the row, the zoom, the scroll or the selection changes.
Item {
    id: lane
    property var track
    property var ruler
    readonly property int pad: 3
    readonly property real mark: Math.max(2, Math.min(5, height / 9))     // a note bar's thickness
    readonly property var picked: backend.picked                           // one read per change
    opacity: track.mute ? 0.45 : 1

    Canvas {
        id: c
        anchors.fill: parent
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        Connections {
            target: lane
            function onTrackChanged() { c.requestPaint() }
            function onPickedChanged() { c.requestPaint() }
        }
        Connections {
            target: lane.ruler
            function onStartChanged() { c.requestPaint() }
            function onPerSecChanged() { c.requestPaint() }
        }

        function bar(ctx, x, y, w, h, color) { ctx.fillStyle = color; ctx.fillRect(x, y, w, h) }

        function paintClip(ctx, b, on, x, w, h) {
            var col = on ? Theme.accent : lane.track.hue
            ctx.globalAlpha = on ? 0.3 : 0.18
            ctx.fillStyle = col; ctx.beginPath(); ctx.roundedRect(x, lane.pad, w, h, 4, 4); ctx.fill()
            ctx.globalAlpha = 1
            ctx.strokeStyle = col; ctx.lineWidth = 1
            ctx.beginPath(); ctx.roundedRect(x + 0.5, lane.pad + 0.5, w - 1, h - 1, 4, 4); ctx.stroke()
            var showLabel = lane.height >= 30
            var peaks = b.peaks || [], n = peaks.length
            if (n > 0) {                                   // the waveform: peaks as bars around the middle
                var ix = x + 2, iw = w - 4, top = lane.pad + (showLabel ? 14 : 2), ih = h - (showLabel ? 16 : 4)
                var pw = iw / n
                ctx.globalAlpha = 0.85; ctx.fillStyle = col
                for (var i = 0; i < n; i++) {
                    var ph = Math.max(1, ih * peaks[i])
                    ctx.fillRect(ix + i * pw, top + (ih - ph) / 2, Math.max(1, pw - 1), ph)
                }
                ctx.globalAlpha = 1
            }
            var fi = Math.min(w, lane.ruler.wOf(b.fadeIn || 0)), fo = Math.min(w, lane.ruler.wOf(b.fadeOut || 0))
            ctx.fillStyle = "rgba(0, 0, 0, 0.4)"                // the corner each fade takes off is shaded
            if (fi > 0) { ctx.beginPath(); ctx.moveTo(x, lane.pad); ctx.lineTo(x + fi, lane.pad); ctx.lineTo(x, lane.pad + h); ctx.closePath(); ctx.fill() }
            if (fo > 0) { ctx.beginPath(); ctx.moveTo(x + w, lane.pad); ctx.lineTo(x + w - fo, lane.pad); ctx.lineTo(x + w, lane.pad + h); ctx.closePath(); ctx.fill() }
            if (on && b.type === "clip") paintHandles(ctx, b, x, w, h, fi, fo)
            if (showLabel && b.label) {
                ctx.save(); ctx.beginPath(); ctx.rect(x + 6, lane.pad, Math.max(0, w - 10), h); ctx.clip()
                ctx.fillStyle = Theme.fg; ctx.font = (Theme.label - 1) + "px '" + uiFont + "'"; ctx.textBaseline = "top"
                ctx.fillText(b.label, x + 6, lane.pad + 2)
                ctx.restore()
            }
        }

        function paintHandles(ctx, b, x, w, h, fi, fo) {   // a selected clip's handles (handles.py): level line,
            var y = lane.pad                                  // edges, fade corners, stretch corner
            ctx.globalAlpha = 0.75; bar(ctx, x, y + Math.round((b.levelY || 0) * (h - 1)), w, 1, Theme.fg); ctx.globalAlpha = 1
            bar(ctx, x, y, 3, h, Theme.accent)
            bar(ctx, x + w - 3, y, 3, h, Theme.accent)
            var knobs = [Math.min(w - 7, fi), Math.max(0, w - 7 - fo)]
            for (var i = 0; i < 2; i++) {
                ctx.fillStyle = Theme.fg; ctx.strokeStyle = Theme.accent; ctx.lineWidth = 1
                ctx.beginPath(); ctx.roundedRect(x + knobs[i] + 0.5, y + 0.5, 6, 6, 2, 2); ctx.fill(); ctx.stroke()
            }
            bar(ctx, x + w - 7, y + h - 7, 7, 7, Theme.accent)
        }

        function paintNote(ctx, b, on, x, w, h) {          // a note or a hit: a bar per lane
            var barH = b.type === "hit" ? lane.mark * 1.8 : lane.mark
            ctx.fillStyle = on ? Theme.accent : lane.track.hue
            var ls = b.lanes || []
            for (var i = 0; i < ls.length; i++) ctx.fillRect(x, lane.pad + ls[i] * (h - barH), w, barH)
        }

        onPaint: {
            var ctx = getContext("2d"); ctx.reset()
            var blocks = lane.track.blocks || [], picked = lane.picked, r = lane.ruler
            var h = lane.height - 2 * lane.pad, n = blocks.length
            for (var pass = 0; pass < 3; pass++) {            // clips under, then the rest, then what is selected
                for (var i = 0; i < n; i++) {
                    var b = blocks[i], on = !!picked[b.id], isClip = b.type === "clip" || b.type === "line" || b.type === "sound"
                    if ((pass === 0 ? !isClip || on : pass === 1 ? isClip || on : !on)) continue
                    var x = Math.round(r.xOf(b.t))
                    var w = b.type === "hit" ? (on ? 3 : 2) : Math.max(2, r.wOf(b.dur) - 1)
                    if (x > width || x + w < 0) continue          // off screen
                    if (isClip) paintClip(ctx, b, on, x, w, h)
                    else paintNote(ctx, b, on, x, w, h)
                }
            }
        }
    }
}
