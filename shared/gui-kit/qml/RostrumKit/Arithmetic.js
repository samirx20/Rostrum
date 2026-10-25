.pragma library
// Sums typed into a number box: 3*4, 12+8, 20/4, 10-3, (2+3)*4, 1,5 (a comma is a decimal point). ONE parser for every
// number box (ValueKinds.parse calls it); plain recursive descent, no eval, so nothing typed can run as code.
// calc(text) -> null when the text is not a sum (a plain number, "2k", "80 %", "L 30": the caller reads those),
//               {value} for a good sum, {error} (plain words) for a sum that cannot be worked out.
// Anything it does not understand is refused; it never drops a symbol and carries on with the rest.

var OPS = { "+": 1, "-": 1, "*": 1, "/": 1, "(": 1, ")": 1 }

function calc(text) {
    var s = String(text).replace(/−/g, "-").replace(/×/g, "*").replace(/÷/g, "/").replace(/\s+/g, "")
    if (!/[*\/()]|,|[0-9.)][+\-]/.test(s)) return null                    // no sign between two things: not a sum
    var toks = [], i = 0
    while (i < s.length) {
        var c = s.charAt(i)
        if (OPS[c]) { toks.push(c); i++; continue }
        var m = /^[0-9]*[.,]?[0-9]+(?:[eE][+\-]?[0-9]+)?|^[0-9]+[.,]?/.exec(s.slice(i))
        if (!m) return { error: "“" + text.trim() + "” has “" + c + "” in it, and a sum can only use numbers and + − × ÷ ( )" }
        toks.push(parseFloat(m[0].replace(",", "."))); i += m[0].length
    }
    var p = 0, bad = ""
    function fail(why) { if (!bad) bad = why; return NaN }
    function atom() {
        var t = toks[p]
        if (t === "-") { p++; return -atom() }
        if (t === "+") { p++; return atom() }
        if (t === "(") { p++; var v = sum(); if (toks[p] !== ")") return fail("a bracket is not closed"); p++; return v }
        if (typeof t === "number") { p++; return t }
        return fail(t === undefined ? "it ends too soon" : "“" + t + "” is in the wrong place")
    }
    function product() {
        var v = atom()
        while (toks[p] === "*" || toks[p] === "/") {
            var op = toks[p++], r = atom()
            if (op === "/" && r === 0) return fail("it divides by zero")
            v = op === "*" ? v * r : v / r
        }
        return v
    }
    function sum() {
        var v = product()
        while (toks[p] === "+" || toks[p] === "-") { var op = toks[p++], r = product(); v = op === "+" ? v + r : v - r }
        return v
    }
    var value = sum()
    if (!bad && p < toks.length) fail("“" + toks[p] + "” is in the wrong place")
    if (bad || !isFinite(value)) return { error: "“" + text.trim() + "” is not a sum I can work out: " + (bad || "the answer is too big") }
    return { value: value }
}
