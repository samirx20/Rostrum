.pragma library

// Colour sums for the pickers, in one place: "#rrggbb" <-> HSV (h, s, v all 0..1), mixing, gradient stops.
function clamp01(x) { return Math.max(0, Math.min(1, x)) }
function parseHex(t) {      // "#rrggbb", "rrggbb", "#rgb" -> "#rrggbb" (lower case), "" when it is not a colour
    var s = String(t).trim().toLowerCase().replace(/^#/, "")
    if (/^[0-9a-f]{3}$/.test(s)) s = s[0] + s[0] + s[1] + s[1] + s[2] + s[2]
    return /^[0-9a-f]{6}$/.test(s) ? "#" + s : ""
}
function rgb(hex) { var h = parseHex(hex) || "#000000"; return [parseInt(h.substr(1, 2), 16), parseInt(h.substr(3, 2), 16), parseInt(h.substr(5, 2), 16)] }
function toHex(r, g, b) {
    var c = function (x) { var n = Math.max(0, Math.min(255, Math.round(x))).toString(16); return n.length < 2 ? "0" + n : n }
    return "#" + c(r) + c(g) + c(b)
}
function hsvHex(h, s, v) {
    var i = Math.floor(h * 6) % 6, f = h * 6 - Math.floor(h * 6)
    var p = v * (1 - s), q = v * (1 - f * s), t = v * (1 - (1 - f) * s)
    var c = [[v, t, p], [q, v, p], [p, v, t], [p, q, v], [t, p, v], [v, p, q]][i]
    return toHex(c[0] * 255, c[1] * 255, c[2] * 255)
}
function hexHsv(hex) {
    var c = rgb(hex), r = c[0] / 255, g = c[1] / 255, b = c[2] / 255
    var mx = Math.max(r, g, b), mn = Math.min(r, g, b), d = mx - mn, h = 0
    if (d > 0) {
        if (mx === r) h = ((g - b) / d + 6) % 6
        else if (mx === g) h = (b - r) / d + 2
        else h = (r - g) / d + 4
    }
    return { h: h / 6, s: mx === 0 ? 0 : d / mx, v: mx }
}
function mix(a, b, t) {
    var x = rgb(a), y = rgb(b)
    return toHex(x[0] + (y[0] - x[0]) * t, x[1] + (y[1] - x[1]) * t, x[2] + (y[2] - x[2]) * t)
}
function shade(hex) { return hexHsv(hex).v < 0.25 ? mix(hex, "#ffffff", 0.6) : mix(hex, "#000000", 0.55) }   // the second stop of a new gradient
function rgba(hex, a) { var c = rgb(hex); return "rgba(" + c[0] + "," + c[1] + "," + c[2] + "," + a + ")" }
function stopAt(stops, at) {    // the colour and opacity a gradient has at `at`
    if (!stops.length) return { color: "#000000", opacity: 1 }
    if (at <= stops[0].at) return { color: stops[0].color, opacity: stops[0].opacity }
    for (var i = 1; i < stops.length; i++) if (at <= stops[i].at) {
        var a = stops[i - 1], b = stops[i], t = b.at === a.at ? 0 : (at - a.at) / (b.at - a.at)
        return { color: mix(a.color, b.color, t), opacity: a.opacity + (b.opacity - a.opacity) * t }
    }
    var l = stops[stops.length - 1]
    return { color: l.color, opacity: l.opacity }
}
function reversed(stops) {
    return stops.map(function (s) { return { at: 1 - s.at, color: s.color, opacity: s.opacity } }).reverse()
}
function sorted(stops) {        // by position; equal positions keep their order
    return stops.map(function (s, i) { return [s, i] }).sort(function (a, b) { return a[0].at - b[0].at || a[1] - b[1] })
                .map(function (p) { return p[0] })
}
function addStops(grad, stops) {    // a canvas gradient gets the stops
    stops.forEach(function (s) { grad.addColorStop(clamp01(s.at), rgba(s.color, s.opacity === undefined ? 1 : s.opacity)) })
}
