import QtQuick
import "."
import "ValueKinds.js" as VK

// A number. Drag sideways to scrub (Shift = coarse, 10 steps at a time; Alt = fine, a tenth of a step), or click to
// type; Up / Down step while typing. Double-click puts it back to `defaultValue` (none set: nothing happens), and the
// mouse wheel changes it only while it has keyboard focus (otherwise the wheel scrolls the panel under it).
// A scrub is one gesture: scrubStarted, many scrubbed(value), scrubEnded — the app records it as ONE change.
// A typed value or an arrow step is one edited(value); a typed value outside from…to is refused (the field turns red and says
// the range, `label` first: "Tempo is 20–400 bpm"), never clamped. Scrubbing, arrows and the wheel stop at the ends. `words` ([{value, label}]): a value that means something
// ("End of comp") shows as its words, not as a number; it can't be scrubbed from (click and type a number instead).
// `expressions`: the app can drive a value by an expression (2D), so a typed "=…" is sent whole as typedExpression
// (the text, "=" included), never stripped to the number in it. Off, "=…" is read as the number it holds.
// `display` ("percent", "db", "pan"; ValueKinds.js): the value is shown, typed, scrubbed and stepped in that kind's
// units ("80 %", "−1.9 dB", "L 30"); what goes out is always the stored value. "" = a plain number with `unit`.
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
    property string display: ""
    property string label: ""                                  // what it is, for the refusal ("Tempo is 20–400 bpm")
    readonly property string word: { for (let w of words) if (w.value === value) return w.label; return "" }
    readonly property bool scrubbing: scrub.scrubbing
    signal edited(real value)
    signal typedExpression(string text)
    signal scrubStarted()
    signal scrubbed(real value)
    signal scrubEnded()

    // scrubbing, arrows and the wheel work on the shown number (`shown`, in steps of `showStep`); clamp() gives it back stored
    readonly property real shown: VK.shown(display, value)
    readonly property real showStep: VK.step(display, step)
    readonly property var showRange: VK.range(display, from, to)
    readonly property int decimals: VK.decimalsOf(showStep)
    readonly property var parts: VK.parts(display, value, step)
    readonly property string unitShown: display ? parts.unit : unit
    readonly property bool unitFirst: /\/$/.test(unitShown)    // "f/2.8"
    readonly property bool hasDefault: defaultValue !== null && defaultValue !== undefined
    function clamp(n, unit) {                                    // a shown number -> the stored value, in range
        const u = unit || showStep
        const k = Math.max(showRange[0], Math.min(showRange[1], Math.round(n / u) * u))
        return Math.max(from, Math.min(to, VK.stored(display, k)))
    }
    function format(v) {                                         // a fine value (Alt) shows its extra digit
        if (display) return parts.text
        let d = decimals
        while (d < decimals + 1 && Math.abs(v * Math.pow(10, d) - Math.round(v * Math.pow(10, d))) > 1e-6) d++
        // never wider than the field has room for beside its unit: fewer decimals (the full value stays in the document
        // and shows again when editing, `fullText`)
        while (d > 0 && !fits(Number(v).toFixed(d).replace("-", "−"))) d--
        return Number(v).toFixed(d).replace("-", "−")      // a real minus, like the rest of the app
    }
    // FontMetrics.advanceWidth(text) reads without writing: a TextMetrics' text set inside the `text` binding looped on itself
    function fits(t) { return metrics.advanceWidth(t) <= roomForText }
    FontMetrics { id: metrics; font: f.input.font }
    readonly property string fullText: {                         // typing starts from every digit the value has
        if (display || word || !isFinite(value)) return ""
        const t = String(Number(Number(value).toFixed(9))).replace("-", "−")
        return t === text ? "" : t
    }
    function reset() { if (hasDefault) { f.edited(Math.max(from, Math.min(to, Number(defaultValue)))); f.input.focus = false } }

    editable: true
    engaged: scrub.scrubbing
    text: word || format(value)
    editText: fullText
    prefix: unitFirst && !word ? unitShown : ""
    suffix: unitFirst || word ? "" : unitShown
    onCommitted: (t) => {
        if (expressions && t.trim().startsWith("=")) { f.typedExpression(t.trim()); return }
        var v = VK.parse(display, t)
        if (isNaN(v)) { input.text = text; return }           // not a number (the words themselves too): keep the value
        const n = VK.shown(display, v), tol = showStep * 1e-6
        if (n < showRange[0] - tol || n > showRange[1] + tol) {   // typed out of range: refused with the range, never clamped
            problem = (label ? label + " is " : "Allowed: ") + refusalRange()
            input.text = text; return
        }
        f.edited(clamp(n))
    }
    function refusalRange() {
        const u = unitShown ? (unitFirst ? "" : " ") + unitShown : ""
        const lo = Number(showRange[0].toFixed(decimals)), hi = Number(showRange[1].toFixed(decimals))
        return (unitFirst ? unitShown : "") + String(lo).replace("-", "−") + "–" + String(hi).replace("-", "−") + (unitFirst ? "" : u)
    }
    onArrow: (d, big) => f.edited(clamp(shownFrom() + d * (big ? 10 : 1) * showStep))
    function shownFrom() { return isFinite(shown) ? shown : showRange[0] }     // −∞ dB steps up from the floor

    WheelHandler {  // a notch = one step (Shift ×10, Alt ÷10); only with keyboard focus, else the panel scrolls
        enabled: f.input.activeFocus && !f.word
        acceptedModifiers: Qt.KeyboardModifierMask   // any: NoModifier is 0, so "None | Shift | Alt" meant Shift+Alt only (S36)
        onWheel: (e) => {
            const notch = (e.angleDelta.y || e.angleDelta.x) / 120
            const unit = e.modifiers & Qt.AltModifier ? f.showStep / 10 : e.modifiers & Qt.ShiftModifier ? f.showStep * 10 : f.showStep
            f.edited(f.clamp(f.shownFrom() + notch * unit, unit))
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
        onPressed: (m) => { startX = lastX = m.x; startValue = f.shownFrom(); travelled = 0; scrubbing = false }
        onPositionChanged: (m) => {
            if (f.word || (!scrubbing && Math.abs(m.x - startX) < 3)) return
            if (!scrubbing) { scrubbing = true; f.scrubStarted() }
            const fine = m.modifiers & Qt.AltModifier, coarse = m.modifiers & Qt.ShiftModifier
            travelled += (m.x - lastX) / Theme.scrubPixels * (fine ? 0.1 : coarse ? 10 : 1)
            lastX = m.x
            f.scrubbed(f.clamp(startValue + travelled * f.showStep, fine ? f.showStep / 10 : f.showStep))
        }
        onReleased: {
            if (scrubbing) { scrubbing = false; f.scrubEnded(); return }
            f.input.forceActiveFocus(); f.input.selectAll(); twice.restart()
        }
        onDoubleClicked: f.reset()
        onCanceled: if (scrubbing) { scrubbing = false; f.scrubEnded() }
    }
}
