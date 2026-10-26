.pragma library
.import "Tempo.js" as Tempo
// A patch of a row's or the roll's blocks (screensound/block_patch.py `apply`, the same rule; JSON text, one per
// change at any count): the blocks whose ids are gone are left out, changed ones take their place, new ones go at
// the end, and the blocks only moved (`by`: [field, d, ids]) are made here from the ones shown, their place shifted by
// d ("beats": atBeat and endBeat, "secs": t): a whole-song move sends ids and a number, not every block again. The
// list made remembers the patch (`__patch`: the list it came from, what it put and took), so a surface that painted
// that list looks only at those blocks (`update`), and where each block sits (`__at`, id -> index, shared while no
// block goes): a hit drawn on a track of 3,000 costs what one block costs, not a walk over all of them on each surface.
function patch(blocks, text, map) {
    var p = JSON.parse(text), put = p.put, gone = p.gone, out, at = _at(blocks), i, j
    var tm = map && map.length && (p.by.length || put.length) ? [_plainMap(map), Tempo.key(map)] : null
    var dt = null, one = gone.length === 0, n = 0                     // every block moved by one time (Slide.js)
    function moved(o, x, plain) {                                   // (plain: moved here, so nothing else changed)
        var s = plain ? o.t - x.t : _shift(o, x)
        if (one) { if (dt === null) dt = s; one = Math.abs(s - dt) < 1e-9 }
        n++
    }
    for (i = 0; i < put.length; i++) {
        if (tm !== null && put[i].atBeat !== undefined) put[i] = _moved(put[i], "beats", 0, tm)
        if (one) moved(put[i], blocks[at[put[i].id]])
    }
    for (i = 0; i < p.by.length; i++) {
        var field = p.by[i][0], d = p.by[i][1], ids = p.by[i][2], all = ids === null    // (null: every block, in order)
        for (j = 0; j < (all ? blocks.length : ids.length); j++) {
            var k = all ? j : at[ids[j]]
            if (!all && (k === undefined || k >= blocks.length || blocks[k].id !== ids[j])) throw new Error("Blocks.patch: no block " + ids[j] + " to move")
            put.push(_moved(blocks[k], field, d, tm))
            if (one) moved(put[put.length - 1], blocks[k], typeof put[put.length - 1].t === "number"
                           && Math.abs((put[put.length - 1].dur || 0) - (blocks[k].dur || 0)) < 1e-9)
        }
    }
    if (put.length === blocks.length && p.by.length === 1 && p.by[0][2] === null) {
        out = put; out.__at = at                     // every block moved, in its place
    } else if (gone.length === 0) {
        out = blocks.slice()
        for (i = 0; i < put.length; i++) {
            j = at[put[i].id]
            if (j !== undefined && j < blocks.length && blocks[j].id === put[i].id) out[j] = put[i]
            else { at[put[i].id] = out.length; out.push(put[i]) }
        }
        out.__at = at
    } else {
        var drop = {}, by = {}
        out = []
        for (i = 0; i < gone.length; i++) drop[gone[i]] = true
        for (i = 0; i < put.length; i++) by[put[i].id] = put[i]
        for (i = 0; i < blocks.length; i++) {
            var b = blocks[i]
            if (drop[b.id]) continue
            if (by[b.id]) { out.push(by[b.id]); delete by[b.id] } else out.push(b)
        }
        for (i = 0; i < put.length; i++) if (by[put[i].id]) out.push(put[i])
    }
    out.__patch = { from: blocks, put: put, gone: gone, dt: one && n === blocks.length && isFinite(dt) ? dt : undefined }
    var was = blocks.__patch                 // the list patched is never painted from now on: what it came from is let go
    if (was !== undefined) { was.from = null; was.put = []; was.gone = [] }    // (else every list since the last whole
    return out                               // send stayed alive: each whole-song Right ~5-10 ms slower than the last)
}

// A block shown, its place moved by d: one placed in beats, timed at once under the map shown (`tm`: [map, its key],
// as `timed` makes it: a layer over its own block, never one more), so `timed` passes it by; one in seconds, a copy.
// A block a patch puts is timed here the same way (d = 0): `timed` copying a list of 3,352 new blocks (Ctrl+D) and
// keeping a map of each cost ~140 ms.
// (Copying each moved block and timing it after cost ~25 µs a block: 0.1 s for a 1,900-note row.)
function _moved(x, field, d, tm) {
    var o
    if (field === "beats" && tm !== null) {
        o = Object.create(x.__tempo !== undefined ? Object.getPrototypeOf(x) : x)
        o.atBeat = x.atBeat + d; o.t = Tempo.seconds(tm[0], o.atBeat)
        if (x.endBeat !== undefined) { o.endBeat = x.endBeat + d; o.dur = Tempo.seconds(tm[0], o.endBeat) - o.t }
        o.__tempo = tm[1]
        return o
    }
    o = {}
    for (var key in x) if (key !== "__tempo") o[key] = x[key]
    if (field === "beats") { o.atBeat = x.atBeat + d; if (x.endBeat !== undefined) o.endBeat = x.endBeat + d }
    else o.t = x.t + d
    return o
}

// The seconds block `o` is `x` moved by (NaN: `x` is none, or anything else changed: what it shows, its length).
// An undo sends a few blocks whole whose new place is not the old one plus the move in floating point (the song's
// times are rounded): those count as moved here, where only the picture is decided.
var PLACE = { t: true, dur: true, atBeat: true, endBeat: true, __tempo: true }
function _shift(o, x) {
    if (x === undefined || typeof o.t !== "number" || Math.abs((o.dur || 0) - (x.dur || 0)) > 1e-9) return NaN
    for (var key in o) {
        if (PLACE[key]) continue
        var a = o[key], b = x[key]
        if (a === b) continue
        if (a === null || b === null || typeof a !== "object" || typeof b !== "object" || a.length === undefined || a.length !== b.length) return NaN
        for (var i = 0; i < a.length; i++) if (a[i] !== b[i]) return NaN
    }
    return o.t - x.t
}

function _at(list) {                     // id -> index (made once per list a patch starts from)
    if (list.__at === undefined) {
        var m = {}
        for (var i = 0; i < list.length; i++) m[list[i].id] = i
        list.__at = m
    }
    return list.__at
}

// The blocks placed in beats (`atBeat`, `endBeat`: timeline.in_beats) with their seconds (`t`, `dur`) from the song's
// tempo map (Tempo.js; backend.song.tempoMap), the others as they are. A block already timed under an equal map is
// the very same object (a patch re-times only what it put, so the painters see only those change); a tempo change
// makes every block placed in beats again, here only: Python sends no row for it (block_patch.seen). A patch's
// record (`__patch`, `__at`) goes with the list, its blocks re-timed the same way.
function timed(list, map) {
    if (!map || !map.length) return list
    var key = Tempo.key(map), out = null, made = null
    if (list.__timed !== undefined && list.__timed[0] === key) return list.__timed[1]    // (a patch dropped: the list shown before)
    map = _plainMap(map)
    for (var i = 0; i < list.length; i++) {
        var x = list[i]
        if (x.atBeat === undefined || x.__tempo === key) continue
        if (out === null) { out = list.slice(); made = new Map() }
        var o = Object.create(x.__tempo !== undefined ? Object.getPrototypeOf(x) : x)   // (a re-timed one: from its own block, never a layer more); its fields read through (a copy of each cost ~30 ms a tempo step)
        o.atBeat = x.atBeat                     // (its own, when it was moved here: `_moved`)
        if (x.endBeat !== undefined) o.endBeat = x.endBeat
        o.t = Tempo.seconds(map, x.atBeat)
        if (x.endBeat !== undefined) o.dur = Tempo.seconds(map, x.endBeat) - o.t
        o.__tempo = key
        out[i] = o; made.set(x, o)
    }
    if (out === null) return list
    var p = list.__patch
    if (p !== undefined) out.__patch = { from: p.from, gone: p.gone, put: p.put.map(function (b) { return made.get(b) || b }) }
    if (list.__at !== undefined) out.__at = list.__at
    list.__timed = [key, out]
    return out
}

// The tempo map as plain JS arrays, read once a call: each read of one from Python goes through Qt (~10 reads a
// block: ~50 µs a block, 0.1 s for a 1,900-note row)
function _plainMap(map) {
    var out = new Array(map.length)
    for (var i = 0; i < map.length; i++) out[i] = Array.prototype.slice.call(map[i])
    return out
}

// A list as sent whole from Python: JSON text (an arrangement row's role, backend.rollBlocks: block_patch.py `text`),
// parsed once into plain blocks; a list (anything else) as `own`.
function parse(sent) {
    return typeof sent === "string" ? (sent === "" ? [] : JSON.parse(sent)) : own(sent || [])
}

// The tempo map as plain JS arrays, read once a call: each read of one from Python goes through Qt (~10 reads a
// block: ~50 µs a block, 0.1 s for a 1,900-note row)
function _plainMap(map) {
    var out = new Array(map.length)
    for (var i = 0; i < map.length; i++) out[i] = Array.prototype.slice.call(map[i])
    return out
}

// A list as sent whole from Python (a row's role, backend.rollBlocks), as a JS array of its blocks, read once. The list
// itself hands out a new object for a block on every read, so a surface's kept entries never matched the blocks of the
// next read: the first edit after every whole send painted the whole surface again (a first note: ~10-20 ms).
function own(list) {
    var out = new Array(list.length)
    for (var i = 0; i < list.length; i++) out[i] = list[i]
    return out
}

// A block's fields as a plain object, made once a block (the painters read only these). A block from Python reads each
// field through the list it came from (~1-2 µs a read): a whole paint of a 1,000-hit drum track read ~10 fields a
// hit, 10-20 ms of every paint. Made when first painted, kept by id while the block stays the same object (up to 3
// copies an id: the same note reaches the row, the roll and the velocity strip as different objects). Not a WeakMap:
// one keyed on the objects that read through Python's lists crashed the app (an access violation in a later click).
var _facts = {}
function fact(b) {
    var held = _facts[b.id] || (_facts[b.id] = [])
    for (var i = 0; i < held.length; i++) if (held[i][0] === b) return held[i][1]
    var f = _plain(b)
    if (held.length >= 3) held.shift()
    held.push([b, f])
    return f
}

function _plain(b) {                     // its lists too (keys, names, peaks …)
    var o = {}
    for (var key in b) { var v = b[key]; o[key] = v === null || typeof v !== "object" ? v : typeof v.length === "number" ? Array.prototype.slice.call(v) : _plain(v) }
    return o
}

// ---- painting in parts (RollNotes, LaneBlocks, VelocityStrip) -------------------------------------------------------
// A surface keeps what its picture shows (`kept()`): an entry per block, [block, selected, order, gone], in the order
// painted, and columns COL px wide (at the zoom and scroll painted) holding the entries over them. After an edit or a
// new selection, `update` finds what changed by looking at each block once (an edit sends new objects only for the
// blocks it changed: the very same object is unchanged) and at the selection's difference, and gives the places each
// changed, added or removed block was and is painted (`rectsOf(block)`: [x, y, w, h] each, margin included). The
// surface paints each place again on its own (`clear`: clipped to it and cleared; then the entries `over` it, in
// order; ctx.restore()): the same picture, with a few blocks painted instead of all of them. A whole repaint grew with
// the track (70 note names ~15 ms a click), and so did comparing every block's state and painting each place over
// every block (~5 ms a surface a click on a 3-minute song). One place at a time: a clip made of several rectangles
// leaves out where they overlap (Canvas clips odd-even). Zoom, scroll, size or layout: one whole paint (`rebuild`).
var COL = 64
var MANY = 32           // more changes than this: one whole paint is as quick

function kept() { return { whole: true, by: {}, count: 0, sel: {}, cols: {}, entries: null, next: 0, stamp: 0, width: 0, picked: null } }

function _place(k, e, rectsOf) {         // the entry into the columns its places reach (on the surface only)
    var rs = rectsOf(e[0])
    for (var i = 0; i < rs.length; i++) {
        var c0 = Math.max(Math.floor(rs[i][0] / COL), -1), c1 = Math.min(Math.floor((rs[i][0] + rs[i][2]) / COL), Math.ceil(k.width / COL))
        for (var c = c0; c <= c1; c++) (k.cols[c] || (k.cols[c] = [])).push(e)
    }
    return rs
}

// Everything kept again, for a whole paint `width` px wide: the entries in the blocks' order. The columns wait until
// a paint in parts needs them (`index`), or the surface is idle (ViewCanvas): a row or roll painted whole on several
// frames running (the Editor opening, a new drum's row) never makes them each time.
function rebuild(k, blocks, picked, rectsOf, width) {
    var out = []
    k.whole = false; k.by = {}; k.sel = {}; k.cols = null; k.width = width; k.rectsOf = rectsOf; k.slid = 0
    for (var i = 0; i < blocks.length; i++) {
        var b = blocks[i], e = [b, !!picked[b.id], i, false, 0]
        k.by[b.id] = e; out.push(e)
        if (e[1]) k.sel[b.id] = true
    }
    k.count = blocks.length; k.next = blocks.length; k.list = blocks; k.entries = out; k.picked = picked
    return out
}

// The columns of the picture painted whole last (where each entry was painted then), made once
function index(k) {
    if (k.cols !== null) return
    var es = k.entries
    k.cols = {}; k.entries = null
    for (var i = 0; i < es.length; i++) if (!es[i][3]) _place(k, es[i], k.rectsOf)
}

// The places to paint again for the blocks and the selection now ([]: none); null: so many that one whole paint is as
// quick (then `rebuild`). Changed blocks keep their place in the order, new ones come last (as `patch`).
function update(k, blocks, picked, rectsOf) {
    index(k)
    var dirty = [], seen = {}, changed = 0, i, e, id
    function mark(rs) {
        for (var j = 0; j < rs.length; j++) { var key = rs[j].join(","); if (!seen[key]) { seen[key] = true; dirty.push(rs[j]) } }
    }
    function took(b) {                   // a block new or changed: where it was and where it is now
        var was = k.by[b.id]
        if (was !== undefined && was[0] === b) return true
        if (++changed > MANY) return false
        var ne = [b, !!picked[b.id], was !== undefined ? was[2] : k.next++, false, 0]
        if (was !== undefined) { was[3] = true; mark(rectsOf(was[0])) }
        k.by[b.id] = ne
        if (ne[1]) k.sel[b.id] = true; else delete k.sel[b.id]
        mark(_place(k, ne, rectsOf))
        return true
    }
    function dropped(id) {               // a block gone: where it was
        var was = k.by[id]
        if (was === undefined) return true
        if (++changed > MANY) return false
        was[3] = true; mark(rectsOf(was[0])); delete k.by[id]; delete k.sel[id]
        return true
    }
    var p = blocks.__patch
    if (p !== undefined && p.from === k.list) {          // a patch of the list painted: only the blocks it names
        for (i = 0; i < p.put.length; i++) if (!took(p.put[i])) return null
        for (i = 0; i < p.gone.length; i++) if (!dropped(p.gone[i])) return null
    } else {
        var n = 0
        for (i = 0; i < blocks.length; i++) {
            if (k.by[blocks[i].id] !== undefined) n++
            if (!took(blocks[i])) return null
        }
        if (n < k.count) {                   // some are gone
            var now = {}
            for (i = 0; i < blocks.length; i++) now[blocks[i].id] = true
            for (id in k.by) if (!now[id] && !dropped(id)) return null
        }
    }
    k.list = blocks
    k.count = blocks.length
    for (id in k.sel) {                      // the selection's difference
        if (picked[id]) continue
        if (++changed > MANY) return null
        e = k.by[id]; e[1] = false; delete k.sel[id]; mark(rectsOf(e[0]))
    }
    for (id in picked) {
        e = k.by[id]
        if (e === undefined || e[1]) continue
        if (++changed > MANY) return null
        e[1] = true; k.sel[id] = true; mark(rectsOf(e[0]))
    }
    k.picked = picked
    return dirty
}

// Does the selection `picked` change what the surface shows? (a click on another track's note leaves it as it is)
function touches(k, picked) {
    if (k.whole) return true
    if (k.picked === picked) return false        // the very selection painted (one shared object a selection)
    for (var id in k.sel) if (!picked[id]) return true
    for (id in picked) { var e = k.by[id]; if (e !== undefined && !e[1]) return true }
    return false
}

// The live entries over the place `d`, in painting order (a column's gone entries are dropped on the way)
function over(k, d) {
    index(k)
    var out = [], st = ++k.stamp, c0 = Math.floor(d[0] / COL), c1 = Math.floor((d[0] + d[2]) / COL)
    for (var c = c0; c <= c1; c++) {
        var col = k.cols[c]
        if (!col) continue
        var live = []
        for (var i = 0; i < col.length; i++) {
            var e = col[i]
            if (e[3]) continue
            live.push(e)
            if (e[4] !== st) { e[4] = st; out.push(e) }
        }
        if (live.length < col.length) k.cols[c] = live
    }
    return out.sort(function (a, b) { return a[2] - b[2] })
}

// [x, y, w, h] around a painted area, `m` px of margin, on whole pixels
function box(x, y, w, h, m) {
    var x0 = Math.floor(x - m), y0 = Math.floor(y - m)
    return [x0, y0, Math.ceil(x + w + m) - x0, Math.ceil(y + h + m) - y0]
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
