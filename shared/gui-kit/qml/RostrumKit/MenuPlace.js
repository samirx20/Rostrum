.pragma library
// One placement rule for every menu and flyout: "open from this button, keep clear of the zones, stay inside the window".
// A zone is any visible item that says `menuAvoid: true` (the tool rail, the timeline's names column) or
// `popupsBeside: true` (the settings panel). A menu that can sit clear of them does; one that cannot overlaps as little as it can.

function collect(item, ov, out) {       // the zones under `item`, as rectangles in `ov`'s coordinates
    if (!item || !item.visible) return out
    if ((item.menuAvoid === true || item.popupsBeside === true) && item.width > 0 && item.height > 0) {
        const p = item.mapToItem(ov, 0, 0)
        out.push({ x: p.x, y: p.y, w: item.width, h: item.height })
        return out
    }
    for (const c of item.children) collect(c, ov, out)
    return out
}

function overlap(a, z) {
    const ox = Math.min(a.x + a.w, z.x + z.w) - Math.max(a.x, z.x)
    const oy = Math.min(a.y + a.h, z.y + z.h) - Math.max(a.y, z.y)
    return ox > 0 && oy > 0 ? ox * oy : 0
}

// prefs: wanted top-left corners, best first. Candidates are those plus, beside each zone, the same row to its left and right.
function pick(zones, W, H, prefs, w, h, gap) {
    const cands = []
    for (const p of prefs) {
        cands.push(p)
        for (const z of zones) { cands.push({ x: z.x - w - gap, y: p.y }); cands.push({ x: z.x + z.w + gap, y: p.y }) }
    }
    let best = null, bestCost = Infinity
    for (const c of cands) {
        const x = Math.max(gap, Math.min(c.x, W - w - gap)), y = Math.max(gap, Math.min(c.y, H - h - gap))
        let cost = Math.abs(x - prefs[0].x) + Math.abs(y - prefs[0].y)
        for (const z of zones) cost += 1000 * overlap({ x: x, y: y, w: w, h: h }, z)
        if (cost < bestCost) { bestCost = cost; best = { x: x, y: y } }
    }
    return best
}

// Under `anchor` (above it when there is no room), edges lined up (`align` "left" or "right"; `x` a fixed left edge instead).
function near(anchor, w, h, root, ov, opts) {
    const o = opts || {}, gap = 8
    const a = anchor.mapToItem(ov, 0, 0)
    const x = o.x !== undefined && !isNaN(o.x) ? o.x : o.align === "right" ? a.x + anchor.width - w : a.x
    const prefs = [{ x: x, y: a.y + anchor.height + 2 }, { x: x, y: a.y - h - 2 }]
    return pick(collect(root, ov, []), ov.width, ov.height, prefs, w, h, gap)
}

// The lowest a panel at [x, x + w) may reach starting at y: just above the first zone under it, else the window's bottom.
function floorBelow(root, ov, x, w, y, gap) {
    let f = ov.height - gap
    for (const z of collect(root, ov, []))
        if (z.y > y && z.x < x + w && z.x + z.w > x) f = Math.min(f, z.y - gap)
    return f
}

// A popup's content lays itself out a moment after it is built (a Column's size is only right after its next polish): a popup
// placed from a size that is not settled yet moves a moment after it shows, under a still pointer. Call this on its content
// item right before placing it (bottom up, every Column / Row / Grid / Flow under it), so it is sized and placed ONCE, before it shows.
function settle(item) {
    if (!item) return
    for (const c of item.children) settle(c)
    if (typeof item.forceLayout === "function") item.forceLayout()
}
