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
// Typing goes through ValueKinds.read (one reader): a number, a sum (1920/3, (100+20)*2, 1,5), or - where the app takes it
// (`relative`) - +20 / *2 / /2 from each layer's own value (editedRelative; "+-45" takes 45 away, "-45" is a plain negative);
// anything else is refused with one sentence. 
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
    property real typeStep: step                               // a typed value keeps this much (a tempo scrubs in 1 bpm but keeps a typed 99.5);
                                                               // 0: all of it (a counter typed 1420.4057 with step 1 was stored 1420, critic 2d-final row 10)
    property string unit: ""
    property var words: []
    property bool expressions: false
    property bool relative: false                              // the app takes +20 / *2 / /2 as from each one's own value (value.set {by})
    property var defaultValue: null                            // the setting's own default; null = none (no reset)
    property string display: ""
    property string label: ""                                  // what it is, for the refusal ("Tempo is 20–400 bpm")
    readonly property string word: { for (let w of words) if (w.value === value) return w.label; return "" }
    readonly property bool scrubbing: scrub.scrubbing
    signal edited(real value)
    signal typedExpression(string text)
    signal editedRelative(real by, real factor)               // +20 (by, in stored units) or *2 / /2 (factor): from each one's own value
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
    // The room its widest value needs (either end of its range), so an amount whose words widen as it moves ("8 %" ->
    // "100 %") never squeezes the slider beside it (InspectorRow; the stability pass caught a 5 px shrink under a click).
    // It only grows while the field shows the same kind of value: a value wider than either end of the range widened
    // it, and the next, shorter one gave the room back, so the slider beside it grew under the click (2D's stability
    // pass). Another kind of value (a reused row) starts again from its own room.
    readonly property real needsNow: {
        const now = metrics.advanceWidth(text) + unitRoom          // the words and unit shown now
        return restNeeds - now + Math.max(now, widestText())
    }
    readonly property string needsKind: display + "|" + from + "|" + to + "|" + unit + "|" + words.length
    property real widestNeeds: 0
    function _grow() { widestNeeds = Math.max(widestNeeds, needsNow) }    // read once the text and its room agree
    onNeedsNowChanged: Qt.callLater(_grow)
    onNeedsKindChanged: { widestNeeds = 0; Qt.callLater(_grow) }
    Component.onCompleted: _grow()
    function endText(v) { return display ? VK.parts(display, v, step).text : Number(v).toFixed(decimals).replace("-", "−") }
    function widestText() {      // either end of the range with its unit, and each word it may show ("Auto" -> "100 %")
        let w = 0
        for (const x of words) w = Math.max(w, metrics.advanceWidth(x.label))
        if (display === "db")   // a level is widest in the middle ("−30.0"), not at its ends ("−∞", "+6.0")
            w = Math.max(w, metrics.advanceWidth("−88.8") + metrics.advanceWidth("dB") + 4)
        if (!isFinite(from) || !isFinite(to) || Math.abs(from) >= 1e8 || Math.abs(to) >= 1e8) return w
        const u = unitShown && !unitFirst ? metrics.advanceWidth(unitShown) + (/^[a-z]/i.test(unitShown) ? 4 : 1) : 0
        return Math.max(w, metrics.advanceWidth(endText(from)) + u, metrics.advanceWidth(endText(to)) + u)
    }
    // FontMetrics.advanceWidth(text) reads without writing: a TextMetrics' text set inside the `text` binding looped on itself
    function fits(t) { return metrics.advanceWidth(t) <= roomForText }
    FontMetrics { id: metrics; font: f.input.font }
    readonly property string fullText: {                         // typing starts from every digit the value has
        if (display || word || !isFinite(value)) return ""
        const t = String(Number(Number(value).toFixed(9))).replace("-", "−")
        return t === text ? "" : t
    }
    // The caret leaves first: leaving commits the shown text (the old value), which must not land after the reset.
    function reset() { if (hasDefault) { f.input.focus = false; f.edited(Math.max(from, Math.min(to, Number(defaultValue)))) } }

    editable: true
    numeric: display === "" || display === "percent"            // dB takes "-inf", pan "L 30" (FieldFrame.cannotUse)
    starts: /^[0-9.,+\-*\/=(]$/                                  // the keys that start typing a number (FieldFrame.typeToStart)
    keepOnRefusal: true
    engaged: scrub.scrubbing
    text: word || format(value)
    editText: fullText
    prefix: unitFirst && !word ? unitShown : ""
    suffix: unitFirst || word ? "" : unitShown
    onCommitted: (t) => {
        if (expressions && t.trim().startsWith("=")) { f.typedExpression(t.trim()); return }
        const r = VK.read(display, t, value)                    // the one reader (ValueKinds.read): a number, a sum, +20 / *2, or why not
        if (relative && (r.by !== undefined || r.factor !== undefined)) { f.editedRelative(r.by === undefined ? 0 : r.by, r.factor === undefined ? 1 : r.factor); return }
        var v = r.value === undefined ? VK.parse(display, t) : r.value   // a leading + * / with no relative form here is a plain sum
        if (isNaN(v)) { problem = t.trim() === "" ? "Type a number" + (label ? " for " + label : "") : VK.BAD; return }   // keep the typed text, and say so
        const n = VK.shown(display, v), tol = showStep * 1e-6
        // dB: the number as typed (−60 dB reads back as −∞, the floor, and is in range); "-inf" is in range when silence is
        const said = display === "db" ? parseFloat(String(t).replace(/−/g, "-").replace(/[^0-9eE+\-.]/g, "")) : n
        const out = isFinite(said) ? said < showRange[0] - tol || said > showRange[1] + tol : v < from || v > to
        if (out) {   // typed out of range: refused with the range, never clamped
            problem = (label ? label + " is " : "Allowed: ") + refusalRange()
            return
        }
        f.edited(typeStep > 0 ? clamp(n, VK.step(display, typeStep)) : clamp(Number(n.toPrecision(12)), 1e-12))
    }
    function refusalRange() {
        const u = unitShown ? (unitFirst ? "" : " ") + unitShown : ""
        const lo = Number(showRange[0].toFixed(decimals)), hi = Number(showRange[1].toFixed(decimals))
        return (unitFirst ? unitShown : "") + String(lo).replace("-", "−") + "–" + String(hi).replace("-", "−") + (unitFirst ? "" : u)
    }
    // A letter the box can't hold that no shortcut took either (typed_word.say_unheard) never vanishes: one line under the
    // box (and in the top bar where the app has one) and one shake (none with Theme.reduceMotion), the typing kept.
    readonly property string letterWords: "Type a number, like 12 or +5"
    function saysLetter(k) {
        letterTip.open(); letterGone.restart()
        if (typeof backend !== "undefined" && backend && backend.tell) backend.tell(letterWords)
        if (Theme.shake > 0) shake.restart()
    }
    Connections {   // a letter that got in as typed (no shortcut took it): taken out again, and said
        target: f.input
        function onTextEdited() {
            const t = f.input.text, at = f.input.cursorPosition, k = t.charAt(at - 1)
            if (f.numeric && /[A-Za-z]/.test(k) && !/[eE]/.test(k) && !f.starts.test(k) && t.indexOf("=") < 0) {
                f.input.remove(at - 1, at); f.saysLetter(k)
            }
        }
    }
    HoverTip { id: letterTip; text: f.letterWords }
    Timer { id: letterGone; interval: 2500; onTriggered: letterTip.close() }
    transform: Translate { id: nudge }
    SequentialAnimation {
        id: shake
        NumberAnimation { target: nudge; property: "x"; to: 4; duration: Theme.shake / 6 }
        NumberAnimation { target: nudge; property: "x"; to: -4; duration: Theme.shake / 3 }
        NumberAnimation { target: nudge; property: "x"; to: 2; duration: Theme.shake / 4 }
        NumberAnimation { target: nudge; property: "x"; to: 0; duration: Theme.shake / 4 }
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
    Connections {   // arriving by Tab: the number is selected, so typing replaces it (a click selects it on release, above)
        target: f.input
        function onActiveFocusChanged() { if (f.input.activeFocus && !scrub.pressed) Qt.callLater(() => { if (!f.input.typed) f.input.selectAll() }) }   // a first key that started the typing (typeToStart) stays
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
            if (justReset) { justReset = false; return }
            f.input.forceActiveFocus(); f.input.selectAll(); twice.restart()
        }
        property bool justReset: false      // the second release of a reset opens no caret
        onDoubleClicked: { justReset = true; f.reset() }
        onCanceled: if (scrubbing) { scrubbing = false; f.scrubEnded() }
    }
}
