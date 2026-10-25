.pragma library
// A patch of a row's or the roll's blocks (screensound/block_patch.py `apply`, the same rule): the blocks whose ids
// are gone are left out, changed ones take their place, new ones go at the end.
function patch(blocks, gone, put) {
    var drop = {}, by = {}, out = [], i
    for (i = 0; i < gone.length; i++) drop[gone[i]] = true
    for (i = 0; i < put.length; i++) by[put[i].id] = put[i]
    for (i = 0; i < blocks.length; i++) {
        var b = blocks[i]
        if (drop[b.id]) continue
        if (by[b.id]) { out.push(by[b.id]); delete by[b.id] } else out.push(b)
    }
    for (i = 0; i < put.length; i++) if (by[put[i].id]) out.push(put[i])
    return out
}

// The ids of a list of blocks, as a set (id -> true): what a lane or the roll holds.
function ids(blocks) {
    var out = {}
    for (var i = 0; i < blocks.length; i++) out[blocks[i].id] = true
    return out
}

// The selected ids (`picked`: id -> true) among `own`, as one string: a lane or the roll is painted again on a new
// selection only when this changed (a click on one track's note leaves every other lane's picture as it was).
function chosen(picked, own) {
    var out = [], ks = Object.keys(picked)
    for (var i = 0; i < ks.length; i++) if (own[ks[i]]) out.push(ks[i])
    return out.sort().join("|")
}

// ---- painting in parts (RollGrid, LaneBlocks, VelocityStrip) -------------------------------------------------------
// A surface keeps `drawn` (id -> [block, selected]) as its picture shows it. After an edit or a new selection,
// `changes` gives the places that changed: where each changed, added or removed block was and is painted
// (`rectsOf(block)`: [x, y, w, h] each, margin included). The surface paints each place again on its own (`clear`:
// clipped to it and cleared; then every block over it, `meets`, in its usual order; ctx.restore()): the same
// picture, with a few blocks painted instead of all of them (a whole repaint grew with the track: 70 note names cost
// ~15 ms a click). One place at a time: a clip made of several rectangles leaves out where they overlap (Canvas
// clips odd-even). Zoom, scroll, size or layout: one whole paint.

// id -> [block, selected] for the blocks now
function state(blocks, picked) {
    var now = {}
    for (var i = 0; i < blocks.length; i++) now[blocks[i].id] = [blocks[i], !!picked[blocks[i].id]]
    return now
}

// [x, y, w, h] around a painted area, `m` px of margin, on whole pixels
function box(x, y, w, h, m) {
    var x0 = Math.floor(x - m), y0 = Math.floor(y - m)
    return [x0, y0, Math.ceil(x + w + m) - x0, Math.ceil(y + h + m) - y0]
}

// The places to paint again since `drawn` (each once); null when so many that one whole paint is as quick.
function changes(drawn, now, rectsOf) {
    var dirty = [], seen = {}, id
    function mark(b) {
        var rs = rectsOf(b)
        for (var i = 0; i < rs.length; i++) { var k = rs[i].join(","); if (!seen[k]) { seen[k] = true; dirty.push(rs[i]) } }
    }
    for (id in now) {
        var was = drawn[id], is = now[id]
        if (!was || was[0] !== is[0] || was[1] !== is[1]) { if (was) mark(was[0]); mark(is[0]) }
    }
    for (id in drawn) if (!(id in now)) mark(drawn[id][0])
    return dirty.length > 32 ? null : dirty
}

// Does a block painted over `rs` reach the place `d`?
function meets(rs, d) {
    for (var i = 0; i < rs.length; i++) {
        var a = rs[i]
        if (a[0] < d[0] + d[2] && d[0] < a[0] + a[2] && a[1] < d[1] + d[3] && d[1] < a[1] + a[3]) return true
    }
    return false
}

// Paint only inside the place `d`, cleared first (ctx.restore() when done)
function clear(ctx, d) {
    ctx.save(); ctx.beginPath(); ctx.rect(d[0], d[1], d[2], d[3]); ctx.clip()
    ctx.clearRect(d[0], d[1], d[2], d[3])
}
