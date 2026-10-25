import QtQuick
import RostrumKit
import "Blocks.js" as Blocks

// One track's things in an arrangement row, drawn only (clicks are the Timeline's): notes as thin bars placed
// by pitch (a chord: one per key), drum hits as ticks placed by drum, recorded clips as blocks with their
// waveform; clips and lines that overlap share the lane in rows (pick.stack); a clip being cleaned fills
// left to right. Every selected one is drawn in the accent colour (backend.picked). `ruler` gives the time mapping.
// One painted surface per row, not a few items per note: a song of 14,000 notes made over a hundred thousand
// items and over a gigabyte of screen memory. Only what is on screen is painted, and it is painted again only
// when the row, the zoom, the scroll or the selection changes.
Item {
    id: lane
    property var track          // the row's layout: hue, mute, group
    property var blocks: []     // its notes / hits / clips (the row model's own role: an edit on them sends only these)
    property var patched: null  // a few of them changed since (backend.blocksPatched): the list as patched
    readonly property var shown: patched || blocks
    onBlocksChanged: patched = null
    Connections {
        target: backend
        function onBlocksPatched(key, gone, put) { if (key === lane.track.id) lane.patched = Blocks.patch(lane.shown, gone, put) }
        function onBlocksReset(key) { if (key === lane.track.id) lane.patched = null }
    }
    property var ruler
    property int slot: 0        // its row: after a resize, rows paint again in turn (ViewCanvas)
    readonly property int pad: 3
    readonly property real mark: Math.max(2, Math.min(5, height / 9))     // a note bar's thickness
    readonly property var picked: backend.picked                           // one read per change
    // Where a block sits across the row (0 top .. 1 bottom), one place per bar: the row's layout places notes by key
    // (`span`) and hits by drum (`drums`), so a new top key or drum relays the row, never every block (pick.lanes,
    // the same rule)
    readonly property var drumAt: { var o = {}, d = track.drums || []; for (var i = 0; i < d.length; i++) o[d[i]] = i; return o }
    function lanesOf(b) {
        if (b.lanes) return b.lanes            // a group header's: placed by its own track's row
        if (b.type === "note") {
            var lo = track.span[0], hi = track.span[1], out = []
            for (var i = 0; i < b.keys.length; i++) out.push(hi === lo ? 0.5 : 1 - (b.keys[i] - lo) / (hi - lo))
            return out
        }
        if (b.type === "hit") return [drumAt[b.drum] / Math.max((track.drums || []).length - 1, 1)]
        return []
    }
    readonly property var cleaning: mixer.cleaning.progress                // clip id -> 0..1 while cleaning
    opacity: track.mute ? 0.45 : track.group ? 0.5 : 1      // a folded group's tracks, faint

    property var cut: ({})        // block ids whose label is cut short (painted last): their whole name shows on hover
    HoverHandler { id: over; onPointChanged: tipAt.x = point.position.x }
    Item { id: tipAt; y: 0; width: 1; height: lane.height
           Loader { id: tipPlace; anchors.fill: parent; active: over.hovered   // made only while hovered: one per lane (H65)
               sourceComponent: HoverTip { parent: tipPlace; hovered: over.hovered; text: {
               over.point.position; const b = lane.shown.find(b => lane.cut[b.id] && b.label
                   && lane.ruler.xOf(b.t) <= over.point.position.x && over.point.position.x <= lane.ruler.xOf(b.t) + lane.ruler.wOf(b.dur))
               return b ? b.label : "" } } } }

    ViewCanvas {   // painted whole on a new zoom, scroll or row look (a resize: stretched, then whole: ViewCanvas), else only where an edit or a selection changed (Blocks.js)
        id: c
        height: parent.height
        ruler: lane.ruler; slot: lane.slot
        property bool whole: true
        readonly property var k: Blocks.kept()  // what the picture shows (painting in parts)
        function again() { whole = true; requestPaint() }
        onWholeWanted: again()
        onHeightChanged: again()
        Connections {
            target: lane
            function onTrackChanged() { c.again() }
            function onShownChanged() { c.requestPaint() }
            function onPickedChanged() { if (Blocks.touches(c.k, lane.picked)) c.requestPaint() }   // a selection elsewhere: as it is
            function onCleaningChanged() { c.again() }
        }
        function widthOf(b, on) { return b.type === "hit" ? (on ? 3 : 2) : Math.max(2, lane.ruler.wOf(b.dur) - 1) }
        function rectsOf(b) {               // a block's column of the row (its bars, or its clip and the clip's handles)
            return [Blocks.box(Math.round(lane.ruler.xOf(b.t)), 0, widthOf(b, true), lane.height, 2)]
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
                ctx.font = (Theme.label - 1) + "px '" + uiFont + "'"
                var room = Math.max(0, w - 10 - tag - (b.canBack || b.canNext ? 38 : 0)), text = b.label
                if (ctx.measureText(text).width > room) {      // cut at a whole letter, with an ellipsis; the whole name on hover
                    lane.cut[b.id] = true
                    while (text.length > 1 && ctx.measureText(text + "…").width > room) text = text.slice(0, -1)
                    text = text.length > 1 || room > 12 ? text + "…" : ""
                } else delete lane.cut[b.id]
                ctx.fillStyle = Theme.fg; ctx.textBaseline = "top"
                ctx.fillText(text, x + 6 + tag, y0 + 2)
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
            var ls = lane.lanesOf(b)
            for (var i = 0; i < ls.length; i++) ctx.fillRect(x, lane.pad + ls[i] * (h - barH), w, barH)
        }

        onPaint: {
            if (waiting) return                                  // the stretched picture stands until its turn
            var ctx = getContext("2d"), dirty = whole ? null : Blocks.update(k, lane.shown, lane.picked, rectsOf)
            whole = false
            if (dirty === null) { markPainted(); ctx.reset(); paintIn(ctx, Blocks.rebuild(k, lane.shown, lane.picked, rectsOf, width), null); return }
            for (var i = 0; i < dirty.length; i++) {            // only the changed places, each cleared and painted again
                Blocks.clear(ctx, dirty[i]); paintIn(ctx, Blocks.over(k, dirty[i]), dirty[i]); ctx.restore()
            }
        }
        function paintIn(ctx, entries, d) {                     // these blocks ([block, selected]; over the place `d`, when one)
            var r = lane.ruler
            var h = lane.height - 2 * lane.pad, n = entries.length
            for (var pass = 0; pass < 3; pass++) {            // clips under, then the rest, then what is selected
                for (var i = 0; i < n; i++) {
                    var b = entries[i][0], on = entries[i][1], isClip = b.type === "clip" || b.type === "line"
                    if ((pass === 0 ? !isClip || on : pass === 1 ? isClip || on : !on)) continue
                    var x = Math.round(r.xOf(b.t))
                    var w = widthOf(b, on)
                    if (x > width || x + w < 0) continue          // off screen
                    if (d !== null && (x - 4 > d[0] + d[2] || x + w + 4 < d[0] || !Blocks.meets(rectsOf(b), d))) continue
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
        model: lane.track.icon === "voice" ? lane.shown.filter(b => b.canBack || b.canNext) : []   // only a voice track has takes: no pass over a long track's blocks on each edit
        TakeArrows { required property var modelData; block: modelData; ruler: lane.ruler; inset: lane.pad + 2 }
    }

    Repeater {   // what an agent just changed here: the 1-second outline (only the flashed blocks get an item)
        model: { const f = backend.agent.flash; return f.length ? lane.shown.filter(b => f.indexOf(b.id) >= 0) : [] }   // one read, not one a block
        ChangeOutline {
            required property var modelData
            x: Math.round(lane.ruler.xOf(modelData.t)); y: lane.pad; height: lane.height - 2 * lane.pad
            width: modelData.type === "hit" ? 3 : Math.max(3, lane.ruler.wOf(modelData.dur) - 1)
        }
    }
}
