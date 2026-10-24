.pragma library

// Keys of one row that would touch on screen become one entry standing for all of them (After Effects does the same
// zoomed out): { t, id, ids, n, members } with t of the first, every key's ids, n = how many, members = the row keys' own ids. Zoom in and they come apart.
// Judged on the pixels the dots are drawn at (`xOf(t)`, rounded), so two dots are never closer than `gap` px, at any
// zoom. Keys at least `gap` px apart stay as they are; a bar's end dots are not slid inward (LayerTrack.qml gives the
// bar room for a whole dot at each end), so they cannot land on a neighbour. A layer's bar already gives one entry per frame (ids).
function group(keys, xOf, gap) {
    const out = []
    let last = null, lastX = 0
    for (const k of keys) {
        if (last && xOf(k.t) - lastX < gap) {
            last.ids = last.ids.concat(k.ids || [k.id]); last.members.push(k.id); last.n += 1; lastX = xOf(k.t)
        } else {
            last = Object.assign({}, k, { ids: (k.ids || [k.id]).slice(), n: 1, members: [k.id] })
            lastX = xOf(k.t)
            out.push(last)
        }
    }
    return out
}

// The same dots as `frozen` (the `members` of each, taken when a drag began), with the keys' new times. A dot is never
// merged, split or reordered while a key is held, so its delegate (and the mouse grab on it) lives to the release.
function regroup(keys, frozen) {
    const byId = {}
    for (const k of keys) for (const i of k.ids || [k.id]) byId[i] = k      // a key dragged onto another's frame shares its entry: both dots stay, one on the other
    const out = []
    for (const m of frozen) {
        const ks = [...new Set(m.map(i => byId[i]))].filter(k => k !== undefined)
        if (ks.length === 0) continue
        out.push(Object.assign({}, ks[0], { ids: ks.reduce((a, k) => a.concat(k.ids || [k.id]), []), n: ks.length, members: ks.map(k => k.id) }))
    }
    return out
}
