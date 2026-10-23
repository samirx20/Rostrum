import QtQuick
import RostrumKit

// One track's things in an arrangement row, drawn only (clicks are the Timeline's): notes as thin bars placed
// by pitch (a chord: one per key), drum hits as ticks placed by drum, recorded clips as blocks with their
// waveform; clips and lines that overlap share the lane in rows (pick.stack); a clip being cleaned fills
// left to right. Every selected one is drawn in the accent colour (backend.picked). `ruler` gives the time mapping.
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
    readonly property var cleaning: mixer.cleaning.progress                // clip id -> 0..1 while cleaning
    opacity: track.mute ? 0.45 : track.group ? 0.5 : 1      // a folded group's tracks, faint

    Canvas {
        id: c
        anchors.fill: parent
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        Connections {
            target: lane
            function onTrackChanged() { c.requestPaint() }
            function onPickedChanged() { c.requestPaint() }
            function onCleaningChanged() { c.requestPaint() }
        }
        Connections {
            target: lane.ruler
            function onStartChanged() { c.requestPaint() }
            function onPerSecChanged() { c.requestPaint() }
        }

        function bar(ctx, x, y, w, h, color) { ctx.fillStyle = color; ctx.fillRect(x, y, w, h) }

        function paintClip(ctx, b, on, x, w, y0, h) {   // y0: its row's top (stacked clips share the lane)
            var col = lane.track.hue                       // selected: an accent outline only, the waveform stays as it was
            ctx.globalAlpha = 0.18
            ctx.fillStyle = col; ctx.beginPath(); ctx.roundedRect(x, y0, w, h, 4, 4); ctx.fill()
            ctx.globalAlpha = 1
            ctx.strokeStyle = on ? Theme.accent : col; ctx.lineWidth = on ? 2 : 1
            ctx.beginPath(); ctx.roundedRect(x + 0.5, y0 + 0.5, w - 1, h - 1, 4, 4); ctx.stroke()
            var showLabel = h >= 16
            var peaks = b.peaks || [], n = peaks.length
            if (n > 0) {                                   // the waveform: peaks as bars around the middle
                var ix = x + 2, iw = w - 4, top = y0 + (showLabel ? 14 : 2), ih = h - (showLabel ? 16 : 4)
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
            if (fi > 0) { ctx.beginPath(); ctx.moveTo(x, y0); ctx.lineTo(x + fi, y0); ctx.lineTo(x, y0 + h); ctx.closePath(); ctx.fill() }
            if (fo > 0) { ctx.beginPath(); ctx.moveTo(x + w, y0); ctx.lineTo(x + w - fo, y0); ctx.lineTo(x + w, y0 + h); ctx.closePath(); ctx.fill() }
            if (on && b.type === "clip") paintHandles(ctx, b, x, w, y0, h, fi, fo)
            var done = lane.cleaning[b.id]
            if (done !== undefined) {                      // its cleaned take being made: fills left to right
                ctx.globalAlpha = 0.35; bar(ctx, x, y0, Math.max(2, w * done), h, Theme.accent); ctx.globalAlpha = 1
                bar(ctx, x, y0 + h - 2, Math.max(2, w * done), 2, Theme.accent)
            }
            if (b.making) {                                // a voice line being spoken: tinted, with a stripe along its bottom
                ctx.globalAlpha = 0.25; bar(ctx, x, y0, w, h, Theme.accent); ctx.globalAlpha = 1
                bar(ctx, x, y0 + h - 2, w, 2, Theme.accent)
            }
            var tag = (b.tie && showLabel) ? 12 : 0         // tied to a project marker (2D's cues): a diamond, then the name
            if (tag > 0 && w > 24) {
                ctx.fillStyle = Theme.fg; ctx.beginPath(); ctx.moveTo(x + 10, y0 + 4); ctx.lineTo(x + 14, y0 + 8)
                ctx.lineTo(x + 10, y0 + 12); ctx.lineTo(x + 6, y0 + 8); ctx.closePath(); ctx.fill()
            } else tag = 0
            if (showLabel && b.label) {
                ctx.save(); ctx.beginPath(); ctx.rect(x + 6 + tag, y0, Math.max(0, w - 10 - tag - (b.canBack || b.canNext ? 38 : 0)), h); ctx.clip()
                ctx.fillStyle = Theme.fg; ctx.font = (Theme.label - 1) + "px '" + uiFont + "'"; ctx.textBaseline = "top"
                ctx.fillText(b.label, x + 6 + tag, y0 + 2)
                ctx.restore()
            }
        }

        function paintHandles(ctx, b, x, w, y0, h, fi, fo) {   // a selected clip's handles (handles.py): level line,
            var y = y0                                        // edges, fade corners, stretch corner
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
                    var b = blocks[i], on = !!picked[b.id], isClip = b.type === "clip" || b.type === "line"
                    if ((pass === 0 ? !isClip || on : pass === 1 ? isClip || on : !on)) continue
                    var x = Math.round(r.xOf(b.t))
                    var w = b.type === "hit" ? (on ? 3 : 2) : Math.max(2, r.wOf(b.dur) - 1)
                    if (x > width || x + w < 0) continue          // off screen
                    if (isClip) {
                        var rows = b.rows || 1, rh = rows > 1 ? (h - (rows - 1)) / rows : h   // stacked: its own row
                        paintClip(ctx, b, on, x, w, lane.pad + (b.row || 0) * (rh + 1), rh)
                    }
                    else paintNote(ctx, b, on, x, w, h)
                }
            }
        }
    }

    Repeater {   // a voice line with several takes: ◂ ▸ on the block itself (TakeArrows.qml)
        model: (lane.track.blocks || []).filter(b => b.canBack || b.canNext)
        TakeArrows { required property var modelData; block: modelData; ruler: lane.ruler; inset: lane.pad + 2 }
    }

    Repeater {   // what an agent just changed here: the 1-second outline (only the flashed blocks get an item)
        model: (lane.track.blocks || []).filter(b => backend.agent.flash.indexOf(b.id) >= 0)
        ChangeOutline {
            required property var modelData
            x: Math.round(lane.ruler.xOf(modelData.t)); y: lane.pad; height: lane.height - 2 * lane.pad
            width: modelData.type === "hit" ? 3 : Math.max(3, lane.ruler.wOf(modelData.dur) - 1)
        }
    }
}
