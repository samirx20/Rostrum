import QtQuick
import RostrumKit
import "Blocks.js" as Blocks
import "Marks.js" as Marks

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
        property bool stale: false          // asked while hidden (the Mixer shows): painted when shown again
        onVisibleChanged: if (visible && stale) { stale = false; requestPaint() }
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
        // What every block of one paint shares, read once per paint (Marks.js puts the notes and hits down from it; a
        // hit's diamond is grid.hitHalf, the size RollInput catches a click on).
        // A name's width is measured once (the font never changes).
        property var widths: ({})
        readonly property string nameFont: "600 " + (Theme.label - 1) + "px '" + uiFont + "'"
        onNameFontChanged: widths = ({})
        function view() {
            var r = grid.ruler, rowH = grid.rowH, hue = grid.roll.hue
            return { x0: r.xOf(0), perSec: r.perSec, rowH: rowH, hi: grid.roll.hi, idx: grid.rowIdx, row: Marks.drumRows(grid.roll.drums),
                     d: grid.hitHalf, H: grid.height, W: width, hue: hue,
                     lit: Qt.lighter(hue, 1.25), accent: Theme.accent, app: Theme.app, widths: widths, clip: paintClip }   // selected: a lighter fill, the accent outline
        }
        function round(ctx, x, y, w, h, r) { ctx.beginPath(); ctx.roundedRect(x, y, w, h, r, r) }
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
            if (height <= 0) { whole = true; return }            // the Editor still opening: painted once it has a size
            var ctx = getContext("2d"), k = view(), at = Marks.rollAt(k)
            var dirty = whole ? null : Blocks.update(kept, n.blocks, n.picked, at)
            whole = false
            if (dirty === null) { markPainted(); ctx.reset() }
            ctx.font = nameFont; ctx.textBaseline = "middle"      // the notes' names (a clip sets its own, saved)
            if (dirty === null) { Marks.rollPaint(ctx, Blocks.rebuild(kept, n.blocks, n.picked, at, width), k, null); return }
            for (var i = 0; i < dirty.length; i++) {        // only the changed places, each cleared and painted again
                Blocks.clear(ctx, dirty[i]); Marks.rollPaint(ctx, Blocks.over(kept, dirty[i]), k, dirty[i]); ctx.restore()
            }
        }
    }
}
