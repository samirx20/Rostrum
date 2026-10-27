.pragma library

// The block view's rules, for QML (BlockView and its parts): where ports sit, which wires are allowed, the add list's
// search. rostrum_gui/blocks.py says the same in Python (apps check a wire there before they make it; agents place
// blocks with it); tests/test_blocks.py runs both on the same cases, so the two never drift.

// layout, in canvas units (a block's own coordinates; the view's zoom scales them)
var WIDTH = 180       // every block
var HEADER = 28       // the label
var LINE = 18         // the grey summary line (and the note), only when there is one
var TOP = 4           // above the first port row
var ROW = 22          // one port row: outputs first, then inputs
var BOTTOM = 6        // under the last row
var PORT = 10         // a port's circle

function hasLine(b) { return !!(b.summary || b.note) }
function rowsTop(b) { return HEADER + (hasLine(b) ? LINE : 0) + TOP }
function height(b) { return rowsTop(b) + ((b.outputs || []).length + (b.inputs || []).length) * ROW + BOTTOM }

// The centre of a port in the block's own coordinates: outputs on the right edge, inputs on the left. null: no such port.
function portAt(b, side, name) {
    var outs = b.outputs || [], ins = b.inputs || []
    var i = (side === "out" ? outs : ins).findIndex(function (p) { return p.name === name })
    if (i < 0) return null
    var row = side === "out" ? i : outs.length + i
    return { x: side === "out" ? WIDTH : 0, y: rowsTop(b) + row * ROW + ROW / 2 }
}

// An output of kind `outKind` may feed an input of `inKind`: the same kind always, others only as `converts` says
// ({"number": ["colour"]}: a number output may feed a colour input).
function compatible(outKind, inKind, converts) {
    if (outKind === inKind) return true
    var to = (converts || {})[outKind]
    return !!to && to.indexOf(inKind) >= 0
}

function blockOf(port) { return port.slice(0, port.lastIndexOf(".")) }

// The blocks reachable from `start` following wires downstream ("down") or upstream ("up"), `start` included.
function reach(wires, start, way) {
    var seen = {}, todo = [start]
    seen[start] = true
    while (todo.length) {
        var at = todo.pop()
        for (var i = 0; i < wires.length; i++) {
            var a = blockOf(wires[i].from), b = blockOf(wires[i].to)
            var next = way === "down" ? (a === at ? b : null) : (b === at ? a : null)
            if (next !== null && !seen[next]) { seen[next] = true; todo.push(next) }
        }
    }
    return seen
}

// A wire from block `fromId` to block `toId` would close a loop (a block feeding itself, through any number of wires).
// The wire it would replace (the input's old one) does not count: it goes.
function makesLoop(wires, fromId, toId, toPort) {
    var kept = toPort ? wires.filter(function (w) { return w.to !== toPort }) : wires
    return !!reach(kept, toId, "down")[fromId]
}

// The input a wire of `outKind` goes into on a new block made from that dropped wire: the first of the same kind, else
// the first it may feed; "" for none.
function firstInput(entry, outKind, converts) {
    var ins = entry.inputs || []
    var same = ins.find(function (p) { return p.kind === outKind })
    if (same) return same.name
    var any = ins.find(function (p) { return compatible(outKind, p.kind, converts) })
    return any ? any.name : ""
}

// The add list: catalogue entries matching the typed words, best first. Ranks: the label starts with the query; every
// word starts a word of the label; every word starts a word of the label, group or `words`. A tie keeps catalogue
// order. `fromKind` (a wire dropped on empty space): only the types with an input that kind may feed.
function rank(entry, q, words) {
    var label = entry.label.toLowerCase()
    if (label.indexOf(q) === 0) return 0
    if (startsAll(words, label)) return 1
    if (startsAll(words, (label + " " + (entry.group || "") + " " + (entry.words || "")).toLowerCase())) return 2
    return -1
}
function startsAll(words, text) {
    return words.every(function (w) {
        var re = new RegExp("(^|[^a-z0-9])" + w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))
        return re.test(text)
    })
}
function feeds(entry, fromKind, converts) {
    return !fromKind || (entry.inputs || []).some(function (p) { return compatible(fromKind, p.kind, converts) })
}
function search(catalogue, query, fromKind, converts) {
    var q = String(query || "").toLowerCase().split(/\s+/).filter(function (w) { return w }).join(" ")
    var words = q ? q.split(" ") : []
    var hits = []
    for (var i = 0; i < catalogue.length; i++) {
        var e = catalogue[i]
        if (!feeds(e, fromKind, converts)) continue
        var r = q ? rank(e, q, words) : 0
        if (r >= 0) hits.push({ r: r, i: i })
    }
    hits.sort(function (a, b) { return a.r - b.r || a.i - b.i })
    return hits.map(function (h) { return catalogue[h.i] })
}
