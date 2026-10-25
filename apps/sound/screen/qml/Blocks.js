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
