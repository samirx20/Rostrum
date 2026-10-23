.pragma library
// The window laid out from the frame outward (SPEC 2d-design-v2 §1.2; the reference is solve() in the mockups'
// build.py). One function, used by AppShell for every app with a frame (`frameAspect`). Two arrangements, the one that
// leaves the least empty canvas wins:
//   "stacked": the timeline across the bottom (wide frames). The timeline gets its least height, the frame fills the
//              height left with M px above and below, spare width widens the settings panel up to its most.
//   "side":    the timeline beside a full-height frame (tall and square frames), at least SIDE_TL px wide; under that
//              the settings panel gives width back down to its least, then the frame narrows.
// All sizes are the body's (under the top bar). `o`: {W, H, aspect, gap (between panels), chromeW / chromeH (what the
// centre column spends that isn't the frame's well: tool rail, padding), tlLeast (the timeline's least height),
// asked: {stacked: {right, bottom}, side: {right, bottom}} (sizes set by hand, -1 = automatic; side.bottom = width)}.
// Returns {kind, right, bottom (stacked: height; side: width), frameW, frameH}.

var M = 16, INSP_MIN = 280, INSP_DEF = 300, INSP_MAX = 380, TL_MAX = 0.45, SIDE_TL = 520

function stacked(o, a) {
    var I = a.right >= 0 ? a.right : INSP_DEF, T = a.bottom >= 0 ? a.bottom : o.tlLeast
    var wellW = o.W - I - o.gap - o.chromeW
    var room = function () { return o.H - T - o.gap - o.chromeH }
    var fw = wellW - 2 * M, fh = fw / o.aspect
    if (a.bottom < 0 && fh + 2 * M <= room())                 // width-bound: the timeline takes the height left
        T = Math.max(o.tlLeast, Math.min(room() + T - fh - 2 * M, TL_MAX * o.H))
    if (fh + 2 * M > room()) {                                // height-bound: spare width goes to the settings panel
        fh = room() - 2 * M; fw = fh * o.aspect
        if (a.right < 0) I += Math.max(0, Math.min(wellW - fw - 2 * M, INSP_MAX - I))
        wellW = o.W - I - o.gap - o.chromeW
    }
    return { kind: "stacked", right: Math.round(I), bottom: Math.round(T), frameW: fw, frameH: fh,
             waste: wellW * room() - fw * fh }
}

function side(o, a) {
    var I = a.right >= 0 ? a.right : INSP_DEF
    var wellH = o.H - o.chromeH, fh = wellH - 2 * M, fw = fh * o.aspect
    var cw = fw + 2 * M + o.chromeW
    var tw = a.bottom >= 0 ? a.bottom : o.W - I - cw - 2 * o.gap
    if (a.bottom < 0 && tw < SIDE_TL) {
        if (a.right < 0) I = Math.max(INSP_MIN, I - (SIDE_TL - tw))
        tw = SIDE_TL
    }
    var wellW = o.W - I - tw - 2 * o.gap - o.chromeW
    if (wellW - 2 * M < fw) { fw = wellW - 2 * M; fh = fw / o.aspect }
    return { kind: "side", right: Math.round(I), bottom: Math.round(tw), frameW: fw, frameH: fh,
             waste: wellW * wellH - fw * fh }
}

function solve(o) {
    var none = { right: -1, bottom: -1 }, asked = o.asked || {}
    var st = stacked(o, asked.stacked || none), sd = side(o, asked.side || none)
    return sd.waste < st.waste ? sd : st
}
