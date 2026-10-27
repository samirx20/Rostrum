import QtQuick
import "."
import "UndoKeys.js" as UndoKeys

// The one field box. Number, text, choice and colour fields are all this frame, so the box, the underline,
// the hover and focus look, the padding and the text (font, size, left-aligned, vertically centred) are drawn
// here only and cannot drift between fields. A field adds an optional `leading` item (colour swatch) and
// `trailing` item (dropdown arrow; it sits in a Row, so give it no anchors), and says whether typing is allowed.
FocusScope {
    id: f
    property string text: ""
    property string prefix: ""          // dim, before the value ("f/")
    property string suffix: ""          // dim, after the value ("mm", "°")
    property string editText: ""        // what typing starts from, when it differs from the shown text (a rounded number's full precision)
    property string placeholder: ""
    property string atRest: ""          // shown at rest in place of the text (a path field: the file's own name)
    property int elide: Text.ElideRight   // how the text at rest is cut
    property bool editable: false       // typing allowed: a click puts the caret in
    property bool engaged: false        // the field says it is in use (scrubbing, list open): accent look
    property bool keepOnRefusal: false  // a refused entry keeps the caret and the typed text, to be fixed (Esc puts the value back)
    property string problem: ""         // a refused entry, said in a sentence: the field shows red until the next edit
    property string _said: ""           // what this box put in the top bar; taken back when the entry is put right
    onProblemChanged: {
        if (typeof backend === "undefined" || !backend) return
        if (problem !== "" && backend.refuse) backend.refuse(problem)
        else if (problem === "" && _said !== "" && backend.unrefuse) backend.unrefuse(_said)
        _said = problem
    }
    // `typeToStart` (a popover's first field: Popover.qml): the box holds the keys without a caret, looks in use, and the first
    // key that types (`starts`: any character; a NumberField's digits and sums) starts typing with it; every other key
    // (Enter, Ctrl+G, Delete …) stays the window's, the same every time it opens (critic 2d-r11).
    property bool typeToStart: false
    property bool numeric: false        // a number box: a key it cannot use (Delete with nothing after the caret, a letter) is the window's (KeyMap)
    property var starts: /^\S$/
    readonly property bool ready: typeToStart && editable && activeFocus && !input.activeFocus
    function startsWith(e) { return ready && !(e.modifiers & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier)) && starts.test(e.text) }
    Keys.onShortcutOverride: (e) => { if (startsWith(e)) e.accepted = true }     // a typed digit is the box's, never a window key
    Keys.onPressed: (e) => {
        if (!startsWith(e)) return
        input.forceActiveFocus()
        input.text = e.text; input.cursorPosition = input.text.length; input.typed = true
        e.accepted = true
    }
    readonly property bool active: engaged || input.activeFocus || ready
    readonly property bool hovered: hoverHandler.hovered
    property alias input: input
    property alias leading: leadingSlot.data
    property alias trailing: trailingSlot.data
    signal committed(string text)       // Enter or focus loss with changed text
    signal typingStarted()              // the caret went in (a settings row holds its item(s) from here) ...
    signal typingEnded()                // ... and left, after its commit (the row lets go)
    signal entered()                    // Enter, whether or not the text changed
    signal arrow(int direction, bool big)  // Up / Down while typing (Shift = big)
    signal escaped()                    // Esc while typing (the typing is dropped first)
    // the unit's own room at the right of the text, so the number is never drawn under it; `roomForText` is what the
    // text itself may take (a number field rounds to fit it)
    readonly property bool hasUnit: suffix !== "" && atRest === ""     // words at rest ("Mixed") stand alone: no unit after them
    readonly property real unitRoom: hasUnit ? unitText.implicitWidth + (/^[a-z]/i.test(f.suffix) ? 4 : 1) : 0
    readonly property real roomForText: width - input.x - Theme.gap - unitRoom - trailingSlot.width - trailingSlot.anchors.rightMargin
    implicitWidth: 140
    implicitHeight: Theme.field
    // the least width its words at rest need uncut ("Mixed", a word value): a narrow box (an amount's) grows to it
    readonly property real restNeeds: Math.ceil(input.x + rest.implicitWidth + unitRoom + Theme.gap + trailingSlot.width + trailingSlot.anchors.rightMargin)

    HoverHandler { id: hoverHandler }

    Rectangle {  // the box: rounded top, square bottom that the underline closes
        id: box
        anchors.fill: parent
        topLeftRadius: Theme.radiusCtl; topRightRadius: Theme.radiusCtl
        bottomLeftRadius: 2; bottomRightRadius: 2
        color: f.active ? Theme.sunken : f.hovered ? Theme.hover : Theme.raised
        Behavior on color { ColorAnimation { duration: Theme.fast } }
    }
    Rectangle {  // the underline: grey at rest, lighter on hover, accent when in use
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
        height: 1
        color: f.problem !== "" ? Theme.danger : f.active ? Theme.accent : f.hovered ? Theme.lineHover : Theme.line
        Behavior on color { ColorAnimation { duration: Theme.fast } }
    }

    Row {
        id: leadingSlot
        anchors.left: parent.left; anchors.leftMargin: children.length ? Theme.grid + 2 : 0
        anchors.verticalCenter: parent.verticalCenter
        spacing: Theme.grid
    }
    Text {
        id: prefixText
        visible: f.prefix !== ""
        anchors.left: leadingSlot.right; anchors.leftMargin: Theme.gap
        anchors.verticalCenter: parent.verticalCenter
        text: f.prefix; color: Theme.fg3; font: input.font
    }
    TextInput {
        id: input
        anchors.left: prefixText.visible ? prefixText.right : leadingSlot.right
        anchors.leftMargin: prefixText.visible ? 1 : Theme.gap
        anchors.right: trailingSlot.left; anchors.rightMargin: Theme.gap + f.unitRoom
        anchors.verticalCenter: parent.verticalCenter
        horizontalAlignment: TextInput.AlignLeft
        color: activeFocus ? Theme.fg : "transparent"     // at rest the elided copy below shows it, from the start
        selectionColor: Theme.accent; selectedTextColor: "white"
        font.pixelSize: Theme.body
        font.family: uiFont
        font.features: { "tnum": 1 }        // digits all one width, so numbers do not wobble while scrubbing
        clip: true
        property bool passing: false    // a key this box cannot use is on its way to the window's shortcut: read-only for that one key press
        readOnly: !f.editable || passing
        activeFocusOnPress: f.editable
        activeFocusOnTab: f.editable        // Tab goes from field to field in the order they lie (X, then Y), never back to the top bar
        selectByMouse: f.editable
        enabled: f.editable
        focus: true
        property string sent: ""        // what was last committed, so Enter + focus loss commit once
        // typing not yet entered; a selection change first makes any field let go, so typing lands on the item it was
        // typed for (rostrum_gui/pending.py: this property marks a kit field)
        readonly property bool pending: activeFocus && text !== f.text && text !== f.editText && text !== sent
        // a handler may put text back (a refused value): `sent` is what the box holds after it, so Enter + the focus
        // loss that follows commit once and never send the put-back text as a new value
        // A key this box cannot use (numeric boxes only): Delete with nothing after the caret, a letter or any key a number never
        // holds. KeyMap lets it through to the window's shortcut (the box lets go first, keeping what was typed).
        function cannotUse(keys) {         // any one of the job's keys (Delete, Backspace): each press is judged by the key itself (below)
            if (!f.numeric) return false
            const at = cursorPosition, sel = selectedText, n = text.length      // read here: the shortcut's `enabled` follows them
            for (const k of keys) {
                const parts = String(k).split("+"), key = parts[parts.length - 1] || "+"
                if (parts.length > 1) continue
                // a letter: not in an expression ("=time*2") nor a number's exponent ("1e3")
                if (key === "Delete" ? (sel === "" && at >= n) : (key.length === 1 && !f.starts.test(key) && !/[eE]/.test(key) && text.indexOf("=") < 0)) return true
            }
            return false
        }
        Timer { id: passTimer; interval: 60; onTriggered: input.passing = false }
        // A focused TextInput claims Delete and every plain key before any shortcut is tried, and its own accept is out of QML's
        // reach. So the window's key filter (rostrum_gui/typed_word.py) asks here first, once per fresh press: for a key this box
        // cannot use the box is read-only for that press, so the shortcut KeyMap allows (cannotUse) runs. A held key never.
        function passKey(k) { if (f.numeric && cannotUse([k])) { passing = true; passTimer.restart() } }
        property bool typed: false      // a key was typed since the caret went in: a value typed again as it already is says so (below)
        onTextEdited: typed = true
        function commit() {
            if (text !== f.text && text !== f.editText && text !== sent) { sent = text; if (f.keepOnRefusal) f.problem = ""; f.committed(text); sent = text }
            else if (typed && f.keepOnRefusal && text !== "" && text !== sent && typeof backend !== "undefined" && backend.tell)   // typed, and as it already is
                backend.tell("Nothing changed: it already is " + f.text + (f.hasUnit ? " " + f.suffix.trim() : "") + ".")
            typed = false
        }
        onAccepted: { commit(); f.entered(); if (!(f.keepOnRefusal && f.problem !== "")) focus = false; else selectAll() }
        onActiveFocusChanged: if (activeFocus) { sent = ""; typed = false; f.problem = ""; if (f.editText !== "") text = f.editText; f.typingStarted() } else { commit(); if (f.keepOnRefusal && f.problem !== "") text = f.text; f.typingEnded() }
        Keys.onEscapePressed: { text = f.text; if (f.keepOnRefusal) f.problem = ""; focus = false; f.escaped() }
        Keys.onUpPressed: (e) => f.arrow(1, (e.modifiers & Qt.ShiftModifier) !== 0)
        Keys.onDownPressed: (e) => f.arrow(-1, (e.modifiers & Qt.ShiftModifier) !== 0)
        // Ctrl+Z / redo with nothing typed here (the box holds its value, or a find box what it found): the window's undo
        Keys.onPressed: (e) => UndoKeys.passOn(e, pending, typeof backend === "undefined" ? null : backend, () => { focus = false })
    }
    Binding {  // the shown text follows the value, except while the person is typing
        target: input; property: "text"; value: f.text
        when: !input.activeFocus
        restoreMode: Binding.RestoreNone
    }
    Text {  // at rest: the text from its start, "…" where it doesn't fit (TextInput would show its end)
        id: rest
        visible: !input.activeFocus
        anchors { left: input.left; right: input.right; verticalCenter: parent.verticalCenter }
        text: f.atRest !== "" ? f.atRest : input.text; elide: f.elide; color: f.problem !== "" ? Theme.danger : Theme.fg; font: input.font
        HoverTip { text: f.problem !== "" ? f.problem : rest.truncated ? rest.text : ""   // the whole value when it is cut
                   hovered: f.hovered || f.problem !== "" }
        Timer { running: f.problem !== ""; interval: 4000; onTriggered: f.problem = "" }
    }
    Text {  // the unit sits right after the value, dim
        id: unitText
        visible: f.hasUnit && input.text !== ""
        x: input.x + Math.min(input.contentWidth, input.width) + (/^[a-z]/i.test(f.suffix) ? 4 : 1)
        anchors.verticalCenter: parent.verticalCenter
        text: f.suffix; color: Theme.fg3; font: input.font
    }
    Text {
        visible: input.text === ""
        anchors.left: input.left; anchors.verticalCenter: parent.verticalCenter
        text: f.placeholder; color: Theme.fg3; font: input.font
    }
    Row {
        id: trailingSlot
        anchors.right: parent.right; anchors.rightMargin: children.length ? Theme.gap : 0
        anchors.verticalCenter: parent.verticalCenter
        spacing: Theme.grid
    }
}
