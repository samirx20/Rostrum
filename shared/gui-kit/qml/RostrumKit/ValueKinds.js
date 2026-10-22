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
    if (kind === "db" && /^-?(inf|∞)/.test(s)) return 0
    if (kind === "pan") {
        if (s === "c" || s === "center" || s === "centre") return 0
        var side = s.charAt(0) === "l" ? -1 : s.charAt(0) === "r" ? 1 : 0
        if (side) s = s.slice(1)
        var n = parseFloat(s.replace(/[^0-9eE+\-.]/g, ""))
        if (isNaN(n)) return NaN
        return stored(kind, side ? side * Math.abs(n) : n)
    }
    var x = parseFloat(s.replace(/[^0-9eE+\-.]/g, ""))
    return isNaN(x) ? NaN : stored(kind, x)
}
