.pragma library
// Numbers and the fader's taper, in one place. The fader runs -60 dB .. +12 dB (gain 0 .. ~3.98; the field's
// range is 0 .. 4); 0 dB (gain 1) sits at 5/6 of the travel. Minus signs are real minus signs.

var FLOOR = -60, SPAN = 72

function num(v, d) {
    if (v === null || v === undefined || isNaN(v)) return "—"
    var s = Math.abs(v).toFixed(d)
    return (v < 0 && Number(s) !== 0 ? "−" : "") + s
}
function dbOf(gain) { return gain > 0 ? 20 * Math.log(gain) / Math.LN10 : -Infinity }
function posOfDb(db) { return Math.max(0, Math.min(1, (db - FLOOR) / SPAN)) }
function posOf(gain) { return posOfDb(dbOf(gain)) }
function gainOf(pos) { return pos <= 0.001 ? 0 : Math.pow(10, (FLOOR + SPAN * Math.min(1, pos)) / 20) }
function faderText(gain) { return gain <= 0.001 ? "−∞ dB" : (dbOf(gain) >= 0.05 ? "+" : "") + num(dbOf(gain), 1) + " dB" }
function panText(p) { var n = Math.round(Math.abs(p) * 100); return n === 0 ? "C" : (p < 0 ? "L " : "R ") + n }

// The level colours, the same on every strip and the master: green below −6 dB, amber −6 .. 0, red over 0.
// Returns the Theme token's name (this file can't see Theme): `Theme[F.levelTone(db)]`.
function levelTone(db) { return db > 0 ? "danger" : db > -6 ? "warn" : "ok" }
// The marks of the fader's dB scale, top to bottom (−∞ sits at the bottom of the travel).
var SCALE = [6, 0, -6, -12, -24, -48, -Infinity]
function scaleText(db) { return db === -Infinity ? "−∞" : db > 0 ? "+" + db : num(db, 0) }

// An effect type's name as the strips show it (strips.py effect_name: the same words): "eq" -> "EQ", "delay" -> "Delay".
var EFFECT_NAMES = { eq: "EQ", deess: "De-ess", dehum: "De-hum" }
function effectName(kind) { return EFFECT_NAMES[kind] || kind.charAt(0).toUpperCase() + kind.slice(1) }
