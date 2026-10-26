.pragma library
// The selection as the painted surfaces read it: one script object per arrangement row (id -> true, that row's
// selected blocks only), made once per selection and shared by every reader, and kept while that row's picks stay the
// same. A map handed over from Python (backend.picked) is copied whole for every reader: ~2.5 ms each with 3,607
// picks, and ~10 readers on every Ctrl+A; each lane then also looked through every pick of the song for its own
// (Blocks.touches / update). Now a lane looks only at its own, and a row whose picks didn't change keeps its very
// object (Blocks.touches: "the very selection painted").
// `stamp` is backend.pickStamp: a reader's binding names it, so it is read again on each change (a new selection, or
// rows that now hold other picks: a note moved to another track).
var _stamp = -1, _rows = {}, _all = null, _heads = null, _backend = null
var EMPTY = ({})

function _sync(backend, stamp) {
    if (stamp === _stamp && backend === _backend) return
    _stamp = stamp; _backend = backend; _all = null; _heads = null
    var got = backend.pickRows(), next = {}
    for (var r in got) {
        var list = got[r], old = _rows[r]
        next[r] = old !== undefined && _same(old.list, list) ? old : { list: list, map: _mapOf(list) }
    }
    _rows = next
}

function _same(a, b) {
    if (a.length !== b.length) return false
    for (var i = 0; i < a.length; i++) if (a[i] !== b[i]) return false
    return true
}

function _mapOf(list) {
    var m = {}
    for (var i = 0; i < list.length; i++) m[list[i]] = true
    return m
}

// One row's selected blocks (EMPTY, one shared object, when none)
function row(backend, stamp, rowId) {
    _sync(backend, stamp)
    var e = _rows[rowId]
    return e !== undefined ? e.map : EMPTY
}

// Every selected id (a surface that is not a row: the velocity strip; a press asking "is it selected?"), made on the
// first ask of a selection
function all(backend, stamp) {
    _sync(backend, stamp)
    if (_all === null) _all = _mapOf(backend.selectedIds)
    return _all
}

// The selected tracks, groups, sections, markers and lines (backend.pickedHeads: no notes, hits or clips): one read a
// selection for every header (~45 of them each read it on every Ctrl+A)
function heads(backend, stamp) {
    _sync(backend, stamp)
    if (_heads === null) _heads = backend.pickedHeads
    return _heads
}
