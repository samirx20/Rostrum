.pragma library
// One way to show each kind of value (a param's `display`): the kit's number field, slider and Python
// (rostrum_gui/value_kinds.py runs this same file) all read and write through these. The stored value never changes;
// only what the person sees and types does. Scrubbing, arrows and the slider work in the shown units (a step of 1 %,
// 0.1 dB, 1 pan point), and every edit goes back through stored().
//   ""        plain number (the field's unit and step decide)
//   percent   stored 0..1 (1 = 100 %), shown "80 %"; typing 80 stores 0.8
//   db        stored as a linear gain (1 = as recorded), shown "−1.9 dB"; 0 is "−∞ dB"; typing -6 stores 0.501
//   pan       stored −1..1, shown "L 30", "C", "R 30"; typing L30, R 30, -30 or 30 (right) works
// Minus signs on screen are real minus signs (−); typing accepts either.
// Typed sums work in every kind: 3*4, 12+8, 20/4, (2+3)*4, 1,5 (Arithmetic.js, the one parser).
.import "Arithmetic.js" as Arith

var KINDS = ["", "percent", "db", "pan"]
var FLOOR = -60                       // dB: at or under this the gain is 0 (the Mixer's fader floor too)
var MINUS = "−"

function num(v, d) {
    var s = Math.abs(v).toFixed(d)
    return (v < 0 && Number(s) !== 0 ? MINUS : "") + s
}
function decimalsOf(step) { return step > 0 ? Math.max(0, Math.ceil(-Math.log(step) / Math.LN10 - 1e-9)) : 0 }

// stored value -> the number in shown units
function shown(kind, v) {
    if (kind === "percent" || kind === "pan") return v * 100
    if (kind === "db") return v > Math.pow(10, FLOOR / 20) ? 20 * Math.log(v) / Math.LN10 : -Infinity
    return v
}
// a number in shown units -> the stored value
function stored(kind, n) {
    if (kind === "percent" || kind === "pan") return n / 100
    if (kind === "db") return n <= FLOOR ? 0 : Math.pow(10, n / 20)
    return n
}
// a field's step (stored units) as a step in shown units
function step(kind, s) {
    if (kind === "percent" || kind === "pan") return Math.max(s * 100, 1)
    if (kind === "db") return 0.1
    return s
}
// a field's range (stored units) in shown units: [lo, hi]
function range(kind, lo, hi) {
    if (kind === "db") return [Math.max(FLOOR, shown(kind, lo)), shown(kind, hi)]
    return [shown(kind, lo), shown(kind, hi)]
}
// an amount: a bounded range that reads well as a slider (pan, a gain, a 0..1 amount; not a ×100 scale)
function slides(kind, lo, hi) {
    return kind === "db" || kind === "pan" || (kind === "percent" && lo >= 0 && hi <= 1)
}

// stored value -> the words on screen ({text, unit}: the field shows the unit as its suffix)
function parts(kind, v, s) {
    if (kind === "percent") return { text: num(Math.round(v * 100 / step(kind, s)) * step(kind, s), decimalsOf(step(kind, s))), unit: "%" }
    if (kind === "db") {
        var db = shown(kind, v)
        if (db === -Infinity) return { text: MINUS + "∞", unit: "dB" }
        return { text: (Math.round(db * 10) >= 1 ? "+" : "") + num(db, 1), unit: "dB" }
    }
    if (kind === "pan") {
        var p = Math.round(Math.abs(v) * 100)
        return { text: p === 0 ? "C" : (v < 0 ? "L " : "R ") + p, unit: "" }
    }
    return { text: num(v, decimalsOf(s)), unit: "" }
}
function format(kind, v, s) {
    var p = parts(kind, v, s === undefined ? 0.01 : s)
    return p.unit ? p.text + " " + p.unit : p.text
}

// typed words -> the stored value (NaN: not a value of this kind)
function parse(kind, t) {
    var s = String(t).replace(/−/g, "-").trim().toLowerCase()
    var sum = kind === "pan" ? null : Arith.calc(s)
    if (sum) return sum.error ? NaN : stored(kind, sum.value)               // 3*4, 12+8, 1,5; a bad sum is refused whole
    if (kind === "db" && /^-?(inf|∞)/.test(s)) return 0
    if (kind === "pan") {
        if (s === "c" || s === "center" || s === "centre") return 0
        var side = s.charAt(0) === "l" ? -1 : s.charAt(0) === "r" ? 1 : 0
        if (side) { s = s.slice(1); sum = Arith.calc(s); if (sum) return sum.error ? NaN : stored(kind, side * Math.abs(sum.value)) }
        var n = parseFloat(s.replace(/[^0-9eE+\-.]/g, ""))
        if (isNaN(n)) return NaN
        return stored(kind, side ? side * Math.abs(n) : n)
    }
    var thousands = /^[+\-]?[\d.]+\s*k(hz)?$/.test(s)          // "2k", "2.5 kHz": thousands (a frequency)
    var x = parseFloat(s.replace(/[^0-9eE+\-.]/g, ""))
    return isNaN(x) ? NaN : stored(kind, thousands ? x * 1000 : x)
}

// The "time" kind (the playhead's box): `current` is {t, fps, duration, markers: [{name, at}]}; the answer is {value: seconds on
// a whole frame} or {error}. 1.5 / 1.5 s seconds, 36f frames, 1:12 minutes:seconds, +12f / -0.5 from the playhead (here a
// leading "-" means back, not a negative time), #name or name a marker. Past either end is refused, never clamped.
function readTime(t, c) {
    var m = /^([+\-])?\s*(?:(\d+(?:[.,]\d+)?)\s*f|(\d+):(\d+(?:[.,]\d+)?)|(\d*[.,]?\d+)\s*s?)$/i.exec(t), at
    if (m) {
        var amount = m[2] !== undefined ? parseFloat(m[2].replace(",", ".")) / c.fps
                   : m[3] !== undefined ? parseInt(m[3], 10) * 60 + parseFloat(m[4].replace(",", ".")) : parseFloat(m[5].replace(",", "."))
        at = m[1] === "+" ? c.t + amount : m[1] === "-" ? c.t - amount : amount
    } else {
        var name = t.replace(/^#\s*/, "").toLowerCase(), hit = null
        for (var i = 0; i < c.markers.length; i++) if (String(c.markers[i].name).toLowerCase() === name) { hit = c.markers[i]; break }
        if (!hit) return { error: "No marker called “" + t.replace(/^#\s*/, "") + "”; a time is 1.5 (seconds), 36f (frames) or 1:12" }
        at = hit.at
    }
    var frame = Math.round(at * c.fps) / c.fps
    if (frame > c.duration + 0.5 / c.fps) return { error: "The scene ends at " + c.duration.toFixed(2) + " s" }
    if (frame < -0.5 / c.fps) return { error: "The scene starts at 0 s" }
    return { value: Math.max(0, Math.min(c.duration, frame)) }
}

var BAD = "Type a number or a sum, like 1920/3; start with = for an expression"
// What a person typed into a box, read once (SPEC base T): {expression: "=…"} (a live expression, the app's own), {value}
// (a plain number or a sum, stored; with `current` an array - a Mixed box - the same value for every one), {value, by}
// / {value, factor} for a relative entry (+20 adds, *2 and /2 scale; `current` a number or an array gives each one's own
// result; `by` stored units, `factor` unitless; "+-45" takes 45 away), or {error}. A leading "-" is a plain negative.
function read(kind, text, current) {
    var t = String(text).replace(/−/g, "-").trim()
    if (kind === "time") return readTime(t, current)
    if (t.charAt(0) === "=") return { expression: t }
    var op = t.charAt(0), rel = op === "+" || op === "*" || op === "/"
    if (rel && kind !== "db") {
        var n = parse(kind === "pan" || kind === "percent" ? "" : kind, t.slice(1))      // the operand in shown units
        if (isNaN(n)) return { error: BAD }
        var by = op === "+" ? stored(kind, n) : 0, factor = op === "*" ? n : op === "/" ? 1 / n : 1
        if (op === "/" && n === 0) return { error: BAD }
        var f = function (c) { return op === "+" ? c + by : c * factor }
        var out = { by: op === "+" ? by : undefined, factor: op === "+" ? undefined : factor }
        if (current !== undefined && current !== null) out.value = typeof current === "object" ? Array.prototype.map.call(current, function (c) { return f(c) }) : f(current)
        return out
    }
    var v = parse(kind, t)
    return isNaN(v) ? { error: BAD } : { value: typeof current === "object" && current !== null ? Array.prototype.map.call(current, function () { return v }) : v }
}
