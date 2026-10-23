.pragma library

// Keys of one row that would touch on screen become one entry standing for all of them (After Effects does the same
// zoomed out): { t, id, ids, n } with t of the first, every key's ids, n = how many. Zoom in and they come apart.
// Keys apart by more than `gap` px stay as they are. A layer's bar already gives one entry per frame (ids).
function group(keys, perSec, gap) {
    const out = []
    let last = null, lastT = 0
    for (const k of keys) {
        if (last && (k.t - lastT) * perSec < gap) {
            last.ids = last.ids.concat(k.ids || [k.id]); last.n += 1; lastT = k.t
        } else {
            last = Object.assign({}, k, { ids: (k.ids || [k.id]).slice(), n: 1 })
            lastT = k.t
            out.push(last)
        }
    }
    return out
}
