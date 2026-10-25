import QtQuick
import RostrumKit
import "Blocks.js" as Blocks

// The piano roll's notes, hits and clips (RollGrid's plot, right of the keys), painted on one surface, not four items
// per note: only what is on screen is painted, whole when the roll's layout, the zoom, the scroll or the size
// changed, else only the places an edit or a selection changed (Blocks.js, painting in parts: a note's name costs
// ~0.2 ms, Canvas draws text as outlines; repainting every name took ~15 ms a click). A selection elsewhere (another
// track's note) leaves the picture as it is.
Item {
    id: n
    property var grid                   // the RollGrid: its roll, blocks, ruler, row height
    clip: true
    readonly property var picked: backend.picked        // one read per change
    readonly property var blocks: grid.blocks
    ViewCanvas {   // a resize: the picture stretched, then painted whole (ViewCanvas)
        id: c
        height: parent.height
        ruler: grid.ruler
        onWholeWanted: again()
        property bool whole: true
        readonly property var kept: Blocks.kept()   // what the picture shows (painting in parts)
        property bool stale: false          // asked while hidden (the Mixer shows): painted when shown again
        onVisibleChanged: if (visible && stale) { stale = false; requestPaint() }
        function again() { whole = true; requestPaint() }
        onHeightChanged: again()
        Connections {
            target: grid
            function onRollChanged() { c.again() }
            function onRowHChanged() { c.again() }
        }
        Connections {
            target: n
            function onBlocksChanged() { c.requestPaint() }
            function onPickedChanged() { if (Blocks.touches(c.kept, n.picked)) c.requestPaint() }   // a selection elsewhere: as it is
        }
        function rectsOf(b, x, k) {         // where a block is painted, 2 px of margin
            if (b.type === "note") {
                var w = Math.max(4, b.dur * k.perSec - 1), out = []
                for (var i = 0; i < b.keys.length; i++) out.push(Blocks.box(x, (k.hi - b.keys[i]) * k.rowH + 1, w, k.rowH - 2, 2))
                return out
            }
            if (b.type === "hit") {
                var cy = grid.roll.drums.indexOf(b.drum) * k.rowH + k.rowH / 2, d = grid.hitHalf
                return [Blocks.box(x - d, cy - d, 2 * d, 2 * d, 2)]
            }
            return [Blocks.box(x, grid.height * 0.2, Math.max(4, b.dur * k.perSec), grid.height * 0.6, 2)]
        }
        // What every note of one paint shares, read once per paint (not once per note): the fills, the row
        // height, the top key, the name font. A name's width is measured once (the font never changes).
        property var widths: ({})
        readonly property string nameFont: "600 " + (Theme.label - 1) + "px '" + uiFont + "'"
        onNameFontChanged: widths = ({})
        function fillOf(on) { return on ? Qt.lighter(grid.roll.hue, 1.25) : grid.roll.hue }      // selected: a lighter fill, the accent outline
        function round(ctx, x, y, w, h, r) { ctx.beginPath(); ctx.roundedRect(x, y, w, h, r, r) }
        function widthOf(ctx, name) {
            var w = widths[name]
            if (w === undefined) { w = ctx.measureText(name).width; widths[name] = w }
            return w
        }
        function paintNote(ctx, b, on, x, k) {
            var w = Math.max(4, b.dur * k.perSec - 1), h = k.rowH - 2, fill = on ? k.lit : k.hue
            for (var i = 0; i < b.keys.length; i++) {
                var y = (k.hi - b.keys[i]) * k.rowH + 1
                ctx.fillStyle = fill; round(ctx, x, y, w, h, 3); ctx.fill()
                if (on) { ctx.strokeStyle = Theme.accent; ctx.lineWidth = 2; round(ctx, x + 1, y + 1, w - 2, h - 2, 2); ctx.stroke() }
                var out = b.out && b.out[i]
                if (out && w >= 10) {      // outside the key playing there: a small dot at the end
                    ctx.fillStyle = Theme.app; ctx.beginPath(); ctx.arc(x + w - 5, y + h / 2, 2.5, 0, 2 * Math.PI); ctx.fill()
                }
                var name = b.names[i]
                if (k.rowH >= 14 && name && w >= widthOf(ctx, name) + (out ? 14 : 5)) {      // whenever the name fits the bar
                    ctx.fillStyle = Theme.app; ctx.fillText(name, x + 3, y + h / 2)
                }
            }
        }
        function paintHit(ctx, b, on, x) {                  // a diamond on its drum's row
            var cy = grid.roll.drums.indexOf(b.drum) * grid.rowH + grid.rowH / 2
            var d = grid.hitHalf
            ctx.globalAlpha = on ? 1 : 0.5 + 0.5 * (b.vel || 0)
            ctx.fillStyle = fillOf(on)
            ctx.beginPath(); ctx.moveTo(x, cy - d); ctx.lineTo(x + d, cy); ctx.lineTo(x, cy + d); ctx.lineTo(x - d, cy); ctx.closePath(); ctx.fill()
            if (on) { ctx.strokeStyle = Theme.accent; ctx.lineWidth = 2; ctx.stroke() }
            ctx.globalAlpha = 1
        }
        function paintClip(ctx, b, on, x) {
            var y = grid.height * 0.2, h = grid.height * 0.6, w = Math.max(4, grid.ruler.wOf(b.dur))
            ctx.strokeStyle = on ? Theme.accent : grid.roll.hue; ctx.lineWidth = 1
            round(ctx, x + 0.5, y + 0.5, w - 1, h - 1, 4); ctx.stroke()
            var peaks = b.peaks || [], n = peaks.length
            if (n > 0) {
                var ix = x + 4, iw = w - 8, top = y + 24, ih = h - 28, pw = iw / n
                ctx.globalAlpha = 0.85; ctx.fillStyle = on ? Theme.accent : grid.roll.hue
                for (var i = 0; i < n; i++) {
                    var ph = Math.max(1, ih * peaks[i])
                    ctx.fillRect(ix + i * pw, top + (ih - ph) / 2, Math.max(1, pw - 2), ph)
                }
                ctx.globalAlpha = 1
            }
            ctx.save(); ctx.beginPath(); ctx.rect(x + 8, y, Math.max(0, w - 16 - (b.canBack || b.canNext ? 38 : 0)), h); ctx.clip()      // the label stays inside its block, clear of the take arrows
            ctx.fillStyle = Theme.fg2; ctx.font = Theme.label + "px '" + uiFont + "'"; ctx.textBaseline = "top"
            var room = Math.max(0, w - 16 - (b.canBack || b.canNext ? 38 : 0)), text = b.label || ""
            if (ctx.measureText(text).width > room) {      // a whole letter, then an ellipsis
                while (text.length > 1 && ctx.measureText(text + "…").width > room) text = text.slice(0, -1)
                text += "…"
            }
            ctx.fillText(text, x + 8, y + 6)
            ctx.restore()
        }
        onPaint: {
            if (!visible) { stale = true; return }
            if (waiting) return                                  // the stretched picture stands until its turn
            var ctx = getContext("2d"), r = grid.ruler
            var k = { perSec: r.perSec, rowH: grid.rowH, hi: grid.roll.hi, hue: grid.roll.hue, lit: fillOf(true), W: width }
            var at = b => rectsOf(b, Math.round(r.xOf(b.t)), k)
            var dirty = whole ? null : Blocks.update(kept, n.blocks, n.picked, at)
            whole = false
            if (dirty === null) { markPainted(); ctx.reset(); paintIn(ctx, Blocks.rebuild(kept, n.blocks, n.picked, at, width), k, null); return }
            for (var i = 0; i < dirty.length; i++) {        // only the changed places, each cleared and painted again
                Blocks.clear(ctx, dirty[i]); paintIn(ctx, Blocks.over(kept, dirty[i]), k, dirty[i]); ctx.restore()
            }
        }
        function paintIn(ctx, entries, k, d) {              // these blocks ([block, selected]; over the place `d`, when one)
            var r = grid.ruler
            ctx.font = nameFont; ctx.textBaseline = "middle"      // the notes' names (a clip sets its own, saved)
            for (var pass = 0; pass < 2; pass++) {          // what is selected is drawn last, on top
                for (var i = 0; i < entries.length; i++) {
                    var b = entries[i][0], on = entries[i][1]
                    if (on !== (pass === 1)) continue
                    var x = Math.round(r.xOf(b.t)), w = b.dur * k.perSec
                    if (x > k.W + 12 || x + w < -12) continue        // off screen
                    if (d !== null && (x - 14 > d[0] + d[2] || x + w + 14 < d[0] || !Blocks.meets(rectsOf(b, x, k), d))) continue
                    if (b.type === "note") paintNote(ctx, b, on, x, k)
                    else if (b.type === "hit") paintHit(ctx, b, on, x)
                    else if (b.type === "clip" || b.type === "line" || b.type === "sound") paintClip(ctx, b, on, x)
                }
            }
        }
    }
}
