.pragma library
// The pointer for each zone of Sound's canvases (CANVAS.md §4), by name: each name is a kit pointer (CURSORS.md),
// [kind, badge], turned by `angle` (degrees, 0 = left-right). A zone shows it with the kit's item (import RostrumCursors):
//     CanvasCursor { kind: Pointers.kind(name); badge: Pointers.badge(name); angle: Pointers.turn(name); altBadge: … }
// The name says what a press does there, so every canvas asks for "trim" or "fade", never for a shape.
var kit = {
    pick: ["pick", ""],                // a body: press picks it, a drag moves it (Alt: a copy, the zone's altBadge)
    moving: ["hand-grab", ""],         // while a move runs
    copy: ["pick", "copy"],            // Alt on a body: a drag copies it
    trim: ["resize", ""],              // a left / right edge: length / trim
    stretch: ["resize", "centre"],     // Alt on a clip's right edge, or its bottom-right corner: stretches in time
    fade: ["resize", ""],              // a clip's top-left corner: fade in
    fadeOut: ["resize", ""],           // its top-right corner: fade out
    level: ["resize", ""],             // a clip's top edge / a velocity bar's top: level
    draw: ["make", ""],                // empty space with Draw, an automation line: a click makes a note / hit / point
    erase: ["pick", "remove"],         // over a note or hit that a click removes (it lights red)
    point: ["pick", "point"],          // an automation point: press picks it, a drag moves it
    bend: ["pick", "bend"]             // between two automation points with Alt: bends the curve
}
var angle = { fade: -45, fadeOut: 45, level: 90 }
function kind(name) { return (kit[name] || kit.pick)[0] }
function badge(name) { return (kit[name] || kit.pick)[1] }
function turn(name) { return angle[name] || 0 }

// The automation point within `tol` px of (x, y): its index, or -1. `xOf` / `yOf` place a point's time / value.
function pointNear(points, xOf, yOf, x, y, tol) {
    var best = -1, d = tol * tol
    for (var i = 0; i < (points || []).length; i++) {
        var dx = xOf(points[i].t) - x, dy = yOf(points[i].v) - y, dd = dx * dx + dy * dy
        if (dd <= d) { d = dd; best = i }
    }
    return best
}

// The arrangement's lanes (LaneBlocks), so the one input area under them (LaneInput) can tell the lane under the
// pointer where it rests (its cut-label tip): a hover handler on each lane took the hover from LaneInput
var _lanes = []
function addLane(lane) { _lanes.push(lane) }
function dropLane(lane) { var i = _lanes.indexOf(lane); if (i >= 0) _lanes.splice(i, 1) }
// `ruler`: the input's own (the lanes of its Timeline); `rowId` "" = over no lane
function hoverLane(ruler, rowId, x) {
    for (var i = 0; i < _lanes.length; i++) {
        var l = _lanes[i]
        if (l.ruler !== ruler) continue
        var on = rowId !== "" && l.rowId === rowId
        if (on) { if (l.hoverX !== x) l.hoverX = x }
        else if (!isNaN(l.hoverX)) l.hoverX = NaN
    }
}

// A move or a length in musical time for a drag's chip: "+1 bar 2 beats", "−3 beats", in the kit's words
// (drag.words_beats, through backend.wordsBeats: one wording for every app)
function beats(backend, n, perBar) { return backend.wordsBeats(n, perBar) }
