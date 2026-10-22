import QtQuick
import "."

// A number. Drag sideways to scrub (Shift = coarse, 10 steps at a time; Alt = fine, a tenth of a step), or click to
// type; Up / Down step while typing. Double-click puts it back to `defaultValue` (none set: nothing happens), and the
// mouse wheel changes it only while it has keyboard focus (otherwise the wheel scrolls the panel under it).
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
    property var defaultValue: null                            // the setting's own default; null = none (no reset)
    readonly property string word: { for (let w of words) if (w.value === value) return w.label; return "" }
    readonly property bool scrubbing: scrub.scrubbing
    signal edited(real value)
    signal typedExpression(string text)
    signal scrubStarted()
    signal scrubbed(real value)
    signal scrubEnded()

    readonly property int decimals: Math.max(0, Math.ceil(-Math.log10(step) - 1e-9))
    readonly property bool unitFirst: /\/$/.test(unit)        // "f/2.8"
    readonly property bool hasDefault: defaultValue !== null && defaultValue !== undefined
    function clamp(v, unit) { const u = unit || step; return Math.max(from, Math.min(to, Math.round(v / u) * u)) }
    function format(v) {                                         // a fine value (Alt) shows its extra digit
        let d = decimals
        while (d < decimals + 1 && Math.abs(v * Math.pow(10, d) - Math.round(v * Math.pow(10, d))) > 1e-6) d++
        return Number(v).toFixed(d)
    }
    function reset() { if (hasDefault) { f.edited(clamp(Number(defaultValue))); f.input.focus = false } }

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

    WheelHandler {  // a notch = one step (Shift ×10, Alt ÷10); only with keyboard focus, else the panel scrolls
        enabled: f.input.activeFocus && !f.word
        acceptedModifiers: Qt.KeyboardModifierMask   // any: NoModifier is 0, so "None | Shift | Alt" meant Shift+Alt only (S36)
        onWheel: (e) => {
            const notch = (e.angleDelta.y || e.angleDelta.x) / 120
            const unit = e.modifiers & Qt.AltModifier ? f.step / 10 : e.modifiers & Qt.ShiftModifier ? f.step * 10 : f.step
            f.edited(f.clamp(f.value + notch * unit, unit))
        }
    }
    Timer { id: twice; interval: Qt.styleHints.mouseDoubleClickInterval }
    MouseArea {  // scrub or start typing; out of the way while the caret is in
        id: scrub
        anchors.fill: parent
        enabled: !f.input.activeFocus || twice.running      // right after the first click, a second one still lands here
        cursorShape: f.word ? Qt.IBeamCursor : Qt.SizeHorCursor
        preventStealing: true
        property bool scrubbing: false
        property real startX: 0
        property real lastX: 0
        property real travelled: 0          // steps moved so far; each move counts at the speed of the keys held now
        property real startValue: 0
        onPressed: (m) => { startX = lastX = m.x; startValue = f.value; travelled = 0; scrubbing = false }
        onPositionChanged: (m) => {
            if (f.word || (!scrubbing && Math.abs(m.x - startX) < 3)) return
            if (!scrubbing) { scrubbing = true; f.scrubStarted() }
            const fine = m.modifiers & Qt.AltModifier, coarse = m.modifiers & Qt.ShiftModifier
            travelled += (m.x - lastX) / Theme.scrubPixels * (fine ? 0.1 : coarse ? 10 : 1)
            lastX = m.x
            f.scrubbed(f.clamp(startValue + travelled * f.step, fine ? f.step / 10 : f.step))
        }
        onReleased: {
            if (scrubbing) { scrubbing = false; f.scrubEnded(); return }
            f.input.forceActiveFocus(); f.input.selectAll(); twice.restart()
        }
        onDoubleClicked: f.reset()
        onCanceled: if (scrubbing) { scrubbing = false; f.scrubEnded() }
    }
}
