.pragma library
.import "Blocks.js" as Blocks
// A move of every block a surface shows by the same time, nothing else changed (a whole-song Right, its undo, its
// redo: Blocks.patch's `dt`), is the picture moved: the surface shifts its pixels by the move and paints only the
// strip the shift uncovers, instead of every block again. Six arrangement rows painted whole made the frame after a
// whole-song Right, undo or redo 100-200 ms on a 3-minute song (a 1,900-note row: 40-90 ms); the shift costs about a
// millisecond a row.
// The picture moves by whole pixels. The shift since the last whole paint is kept (`slid`, in px), each move rounds
// that total, so a block is never more than the rounding (1 px) from where a whole paint would put it: inside the
// 2 px margin every later paint in parts clears around a block (Blocks.box).

// After the move: [[place, the entries over it], …] to paint (cleared, as Blocks.update's places are), or null when
// `blocks` is not the list painted moved as one (paint as before: Blocks.update). The kept entries follow the moved
// blocks; their columns are made again when next needed (Blocks.index).
function slide(k, ctx, blocks, picked, x0, perSec, W, H) {
    var p = blocks.__patch, i, e
    if (k.whole || p === undefined || p.dt === undefined || p.from !== k.list || blocks.length !== k.count
            || Blocks.touches(k, picked)) return null
    var es = new Array(blocks.length)
    for (i = 0; i < blocks.length; i++) {
        e = k.by[blocks[i].id]
        if (e === undefined) return null
        es[i] = e
    }
    for (i = 0; i < es.length; i++) es[i][0] = blocks[i]
    k.list = blocks; k.entries = es; k.cols = null
    var was = k.slid || 0
    k.slid = was + p.dt * perSec
    var dx = Math.round(k.slid) - Math.round(was)
    if (dx === 0) return []
    var img = ctx.getImageData(0, 0, W, H)        // (Qt's putImageData paints nothing here: drawn as an image)
    ctx.clearRect(0, 0, W, H)
    ctx.drawImage(img, dx, 0)
    var d = dx > 0 ? [0, 0, dx + 1, H] : [W + dx - 1, 0, 1 - dx, H]
    return [[d, _over(es, d, x0, perSec)]]
}

// The entries whose block may reach the place `d` (a margin for a hit's diamond and a note's outline: each surface's
// paint checks exactly), in painting order
function _over(es, d, x0, perSec) {
    var out = [], lo = d[0] - 16, hi = d[0] + d[2] + 16
    for (var i = 0; i < es.length; i++) {
        var b = es[i][0], x = x0 + b.t * perSec
        if (x <= hi && x + Math.max(b.dur || 0, 0) * perSec >= lo) out.push(es[i])
    }
    return out.sort(function (a, b) { return a[2] - b[2] })
}
