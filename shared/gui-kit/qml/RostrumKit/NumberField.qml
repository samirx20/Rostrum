import QtQuick
import "."

// A number. Drag sideways to scrub (Shift = 10 steps at a time), or click to type; Up / Down step while typing.
// A scrub is one gesture: scrubStarted, many scrubbed(value), scrubEnded — the app records it as ONE change.
// A typed value or an arrow step is one edited(value). `words` ([{value, label}]): a value that means something
// ("End of comp") shows as its words, not as a number; it can't be scrubbed from (click and type a number instead).
// `expressions`: the app can drive a value by an expression (2D), so a typed "=…" is sent whole as typedExpression
// (the text, "=" included), never stripped to the number in it. Off, "=…" is read as the number it holds.
FieldFrame {
    id: f
    property real value: 0
    property real from: -1e9
    property real to: 1e9
    property real step: 1
    property string unit: ""
    property var words: []
    property bool expressions: false
    readonly property string word: { for (let w of words) if (w.value === value) return w.label; return "" }
    readonly property bool scrubbing: scrub.scrubbing
    signal edited(real value)
    signal typedExpression(string text)
    signal scrubStarted()
    signal scrubbed(real value)
    signal scrubEnded()

    readonly property int decimals: Math.max(0, Math.ceil(-Math.log10(step) - 1e-9))
    readonly property bool unitFirst: /\/$/.test(unit)        // "f/2.8"
    function clamp(v) { return Math.max(from, Math.min(to, Math.round(v / step) * step)) }
    function format(v) { return Number(v).toFixed(decimals) }

    editable: true
    engaged: scrub.scrubbing
    text: word || format(value)
    prefix: unitFirst && !word ? unit : ""
    suffix: unitFirst || word ? "" : unit
    onCommitted: (t) => {
        if (expressions && t.trim().startsWith("=")) { f.typedExpression(t.trim()); return }
        var v = parseFloat(t.replace(/[^0-9eE+\-.]/g, ""))
        if (isNaN(v)) { input.text = text; return }           // not a number (the words themselves too): keep the value
        f.edited(clamp(v))
    }
    onArrow: (d, big) => f.edited(clamp(value + d * (big ? 10 : 1) * step))

    MouseArea {  // scrub or start typing; out of the way while the caret is in
        id: scrub
        anchors.fill: parent
        enabled: !f.input.activeFocus
        cursorShape: f.word ? Qt.IBeamCursor : Qt.SizeHorCursor
        preventStealing: true
        property bool scrubbing: false
        property real startX: 0
        property real startValue: 0
        onPressed: (m) => { startX = m.x; startValue = f.value; scrubbing = false }
        onPositionChanged: (m) => {
            var dx = m.x - startX
            if (f.word || (!scrubbing && Math.abs(dx) < 3)) return
            if (!scrubbing) { scrubbing = true; f.scrubStarted() }
            var steps = Math.round(dx / Theme.scrubPixels) * (m.modifiers & Qt.ShiftModifier ? 10 : 1)
            f.scrubbed(f.clamp(startValue + steps * f.step))
        }
        onReleased: {
            if (scrubbing) { scrubbing = false; f.scrubEnded(); return }
            f.input.forceActiveFocus(); f.input.selectAll()
        }
        onCanceled: if (scrubbing) { scrubbing = false; f.scrubEnded() }
    }
}
