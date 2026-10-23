.pragma library

// Keys of one row that would touch on screen become one entry standing for all of them (After Effects does the same
// zoomed out): { t, id, ids, n } with t of the first, every key's ids, n = how many. Zoom in and they come apart.
// Judged on the pixels the dots are drawn at (`xOf(t)`, rounded), so two dots are never closer than `gap` px, at any
// zoom. Keys at least `gap` px apart stay as they are; a bar's end dots are not slid inward (LayerTrack.qml gives the
// bar room for a whole dot at each end), so they cannot land on a neighbour. A layer's bar already gives one entry per frame (ids).
function group(keys, xOf, gap) {
    const out = []
    let last = null, lastX = 0
    for (const k of keys) {
        if (last && xOf(k.t) - lastX < gap) {
            last.ids = last.ids.concat(k.ids || [k.id]); last.n += 1; lastX = xOf(k.t)
        } else {
            last = Object.assign({}, k, { ids: (k.ids || [k.id]).slice(), n: 1 })
            lastX = xOf(k.t)
            out.push(last)
        }
    }
    return out
}
