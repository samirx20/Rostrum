.pragma library
.import "Blocks.js" as Blocks
// How each note, hit and velocity bar of the painted surfaces (RollNotes, VelocityStrip, LaneBlocks) is put down, as
// plain JavaScript. A call into a surface's own QML function, or a read of a QML property, costs microseconds; done
// per block (its place, its colour, the ruler's xOf) it made a whole paint of a 1,000-hit drum track take 35-60 ms.
// A surface reads what a paint needs once (`k`, its view: where time 0 sits, px per second, row height, colours,
// the drums' rows) and these functions use only that. Clips stay the surface's own (few, with text).

function xOf(b, k) { return Math.round(k.x0 + b.t * k.perSec) }

function drumRows(drums) {               // drum name -> its row
    var row = {}, ds = drums || []
    for (var i = 0; i < ds.length; i++) row[ds[i]] = i
    return row
}

// ---- the Editor's roll ----------------------------------------------------------------------------------------------
// k: x0, perSec, rowH, hi, row (drum -> row), d (a diamond's half), H, hue, lit, accent, app, rowH, widths, clip(ctx, b, on, x)

function rollRects(b, x, k) {            // where a block is painted, 2 px of margin
    if (b.type === "note") {
        var w = Math.max(4, b.dur * k.perSec - 1), out = []
        for (var i = 0; i < b.keys.length; i++) out.push(Blocks.box(x, (k.hi - b.keys[i]) * k.rowH + 1, w, k.rowH - 2, 2))
        return out
    }
    if (b.type === "hit") {
        var cy = k.row[b.drum] * k.rowH + k.rowH / 2
        return [Blocks.box(x - k.d, cy - k.d, 2 * k.d, 2 * k.d, 2)]
    }
    return [Blocks.box(x, k.H * 0.2, Math.max(4, b.dur * k.perSec), k.H * 0.6, 2)]
}
function rollAt(k) { return function (b) { b = Blocks.fact(b); return rollRects(b, xOf(b, k), k) } }

function _round(ctx, x, y, w, h, r) { ctx.beginPath(); ctx.roundedRect(x, y, w, h, r, r) }

function _nameWidth(ctx, k, name) {      // measured once a name (the font never changes between)
    var w = k.widths[name]
    if (w === undefined) { w = ctx.measureText(name).width; k.widths[name] = w }
    return w
}

function _note(ctx, b, on, x, k) {
    var w = Math.max(4, b.dur * k.perSec - 1), h = k.rowH - 2, fill = on ? k.lit : k.hue
    for (var i = 0; i < b.keys.length; i++) {
        var y = (k.hi - b.keys[i]) * k.rowH + 1
        ctx.fillStyle = fill; _round(ctx, x, y, w, h, 3); ctx.fill()
        if (on) { ctx.strokeStyle = k.accent; ctx.lineWidth = 2; _round(ctx, x + 1, y + 1, w - 2, h - 2, 2); ctx.stroke() }
        var out = b.out && b.out[i]
        if (out && w >= 10) {      // outside the key playing there: a small dot at the end
            ctx.fillStyle = k.app; ctx.beginPath(); ctx.arc(x + w - 5, y + h / 2, 2.5, 0, 2 * Math.PI); ctx.fill()
        }
        var name = b.names[i]
        if (k.rowH >= 14 && name && w >= _nameWidth(ctx, k, name) + (out ? 14 : 5)) {      // whenever the name fits the bar
            ctx.fillStyle = k.app; ctx.fillText(name, x + 3, y + h / 2)
        }
    }
}

// The blocks of `entries` ([block, selected]; over the place `d`, when one): selected ones last, on top. A hit is a
// diamond on its drum's row, as strong as it is loud (the colour and the strength set only when they change).
function rollPaint(ctx, entries, k, d) {
    var alpha = 1, fill = null, dd = k.d
    for (var pass = 0; pass < 2; pass++) {
        for (var i = 0; i < entries.length; i++) {
            var b = Blocks.fact(entries[i][0]), on = entries[i][1]
            if (on !== (pass === 1)) continue
            var x = Math.round(k.x0 + b.t * k.perSec), w = b.dur * k.perSec
            if (x > k.W + 12 || x + w < -12) continue        // off screen
            if (d !== null && (x - 14 > d[0] + d[2] || x + w + 14 < d[0] || !Blocks.meets(rollRects(b, x, k), d))) continue
            if (b.type === "hit") {
                var a = on ? 1 : 0.5 + 0.5 * (b.vel || 0), col = on ? k.lit : k.hue, cy = k.row[b.drum] * k.rowH + k.rowH / 2
                if (a !== alpha) { ctx.globalAlpha = a; alpha = a }
                if (col !== fill) { ctx.fillStyle = col; fill = col }
                ctx.beginPath(); ctx.moveTo(x, cy - dd); ctx.lineTo(x + dd, cy); ctx.lineTo(x, cy + dd); ctx.lineTo(x - dd, cy); ctx.closePath(); ctx.fill()
                if (on) { ctx.strokeStyle = k.accent; ctx.lineWidth = 2; ctx.stroke() }
                continue
            }
            if (alpha !== 1) { ctx.globalAlpha = 1; alpha = 1 }
            fill = null
            if (b.type === "note") _note(ctx, b, on, x, k)
            else if (b.type === "clip" || b.type === "line" || b.type === "sound") k.clip(ctx, b, on, x)
        }
    }
    if (alpha !== 1) ctx.globalAlpha = 1
}

// ---- the velocity strip ---------------------------------------------------------------------------------------------
// k: x0, perSec, H, W, top (the bars' foot), plotH, hue, accent

function velAt(k) {                      // a bar's column (its grip reaches 3 px around it)
    return function (b) { b = Blocks.fact(b); return b.type === "note" || b.type === "hit" ? [Blocks.box(Math.round(k.x0 + b.t * k.perSec) - 3, 0, 7, k.H, 2)] : [] }
}

function velPaint(ctx, entries, k, d) {
    for (var pass = 0; pass < 2; pass++) {               // selected bars last, on top
        ctx.fillStyle = pass === 1 ? k.accent : k.hue; ctx.globalAlpha = pass === 1 ? 1 : 0.8
        for (var i = 0; i < entries.length; i++) {
            var b = Blocks.fact(entries[i][0])
            if (b.type !== "note" && b.type !== "hit") continue
            if (entries[i][1] !== (pass === 1)) continue
            var x = Math.round(k.x0 + b.t * k.perSec)
            if (x < -4 || x > k.W + 4) continue
            if (d !== null && (x + 6 < d[0] || x - 6 > d[0] + d[2])) continue
            var h = Math.max(2, b.vel * k.plotH), y = k.top - h
            ctx.fillRect(x - 1, y, 3, h)
            ctx.beginPath(); ctx.arc(x + 0.5, y, 3, 0, 2 * Math.PI); ctx.fill()   // the grip
        }
    }
    ctx.globalAlpha = 1
}

// ---- an arrangement row ---------------------------------------------------------------------------------------------
// k: x0, perSec, H, W, pad, mark (a note bar's thickness), lo, hi (the key span), row (drum -> row), rows, hue, accent,
// clip(ctx, b, on, x, w, y0, h)

function laneWidth(b, on, k) { return b.type === "hit" ? (on ? 3 : 2) : Math.max(2, b.dur * k.perSec - 1) }
function laneAt(k) { return function (b) { b = Blocks.fact(b); return [Blocks.box(xOf(b, k), 0, laneWidth(b, true, k), k.H, 2)] } }

// Clips under, then notes and hits (a bar per lane, 0 top .. 1 bottom of the row: by key, by drum, or a group
// header's own `lanes`), then what is selected
function lanePaint(ctx, entries, k, d) {
    var h = k.H - 2 * k.pad, n = entries.length, fill = null
    for (var pass = 0; pass < 3; pass++) {
        for (var i = 0; i < n; i++) {
            var b = Blocks.fact(entries[i][0]), on = entries[i][1], isClip = b.type === "clip" || b.type === "line"
            if ((pass === 0 ? !isClip || on : pass === 1 ? isClip || on : !on)) continue
            var x = Math.round(k.x0 + b.t * k.perSec), w = laneWidth(b, on, k)
            if (x > k.W || x + w < 0) continue          // off screen
            if (d !== null && (x - 4 > d[0] + d[2] || x + w + 4 < d[0] || !Blocks.meets([Blocks.box(x, 0, laneWidth(b, true, k), k.H, 2)], d))) continue
            if (isClip) {
                var rows = b.rows || 1, rh = rows > 1 ? (h - (rows - 1)) / rows : h   // stacked: its own row
                k.clip(ctx, b, on, x, w, k.pad + (b.row || 0) * (rh + 1), rh); fill = null
                continue
            }
            var col = on ? k.accent : k.hue
            if (col !== fill) { ctx.fillStyle = col; fill = col }
            var bh = b.type === "hit" ? k.mark * 1.8 : k.mark, ls = b.lanes
            if (ls) { for (var j = 0; j < ls.length; j++) ctx.fillRect(x, k.pad + ls[j] * (h - bh), w, bh) }
            else if (b.type === "hit") ctx.fillRect(x, k.pad + k.row[b.drum] / k.rows * (h - bh), w, bh)
            else if (b.type === "note")
                for (j = 0; j < b.keys.length; j++)
                    ctx.fillRect(x, k.pad + (k.hi === k.lo ? 0.5 : 1 - (b.keys[j] - k.lo) / (k.hi - k.lo)) * (h - bh), w, bh)
        }
    }
}
