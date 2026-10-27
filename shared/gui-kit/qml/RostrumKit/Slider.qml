import QtQuick
import "."
import "ValueKinds.js" as VK

// A slider. Pressing on it jumps there and dragging follows: the whole press-to-release is one gesture
// (scrubStarted, scrubbed(value)…, scrubEnded), recorded by the app as ONE change. Left / Right step: edited(value).
// Keys held while dragging: Alt = fine (the drag moves the value at a tenth of the speed, from where Alt went down; no
// jump on press), Shift = coarse (the value lands on every 10th step). Same for Left / Right and the wheel.
// Double-click puts it back to `defaultValue` (edited(default); none set: nothing happens). The wheel changes it only
// while the keyboard stepped to it (Tab) and the panel has not scrolled since: a slider you merely pressed or dragged keeps
// the keyboard for its arrows, but the wheel over it scrolls the panel past it.
// `display` (ValueKinds.js): the travel and the steps are in the shown units (a gain's slider runs in dB, −60 to the
// top, like the Mixer's fader); what goes out is always the stored value.
Item {
    id: s
    property real value: 0
    property real from: 0
    property real to: 1
    property real step: 0.01
    property var defaultValue: null                  // the setting's own default; null = none (no reset)
    property string display: ""
    property var origin: null                        // the value the filled part starts from (pan: 0, fills from the centre); null = from the left end
    readonly property var showRange: VK.range(display, from, to)          // [lo, hi] in shown units
    readonly property real showStep: VK.step(display, step)
    readonly property real shown: { const n = VK.shown(display, value); return isFinite(n) ? n : showRange[0] }
    readonly property bool hovered: hoverHandler.hovered
    readonly property bool pressed: drag.pressed
    readonly property real ratio: showRange[1] > showRange[0] ? (Math.max(showRange[0], Math.min(showRange[1], shown)) - showRange[0]) / (showRange[1] - showRange[0]) : 0
    readonly property real originRatio: {
        if (origin === null || origin === undefined || showRange[1] <= showRange[0]) return 0
        const n = VK.shown(display, Number(origin))
        return isFinite(n) ? Math.max(0, Math.min(1, (n - showRange[0]) / (showRange[1] - showRange[0]))) : 0
    }
    signal edited(real value)
    signal scrubStarted()
    signal scrubbed(real value)
    signal scrubEnded()
    implicitWidth: 140; implicitHeight: Theme.field
    activeFocusOnTab: true
    // The keys it steps with while the person has it (a click gives it the keyboard): the window's own shortcuts leave them (OpenPopups.takes)
    property var ownKeys: ["Left", "Right", "Shift+Left", "Shift+Right", "Alt+Left", "Alt+Right"]

    function clamp(n, unit) {                        // a shown number -> the stored value, in range
        const u = unit || showStep
        const k = Math.max(showRange[0], Math.min(showRange[1], Math.round((n - showRange[0]) / u) * u + showRange[0]))
        return Math.max(from, Math.min(to, VK.stored(display, k)))
    }
    function ratioAt(x) { return Math.max(0, Math.min(1, (x - knob.width / 2) / (width - knob.width))) }
    function unitFor(mods) { return mods & Qt.AltModifier ? showStep / 10 : mods & Qt.ShiftModifier ? showStep * 10 : showStep }
    function nudge(n, mods) { const u = unitFor(mods); edited(clamp(shown + n * u, u)) }
    // A number typed while it has the keyboard (a click on the slider gave it) goes to the value box beside it
    // (`typed`, the first key starting the typing), never nowhere: Drawn so far's typed 0 was lost (2D final critic).
    signal typed(string text)
    property bool forwardsTyping: false              // a row with a value box beside it says so (InspectorRow's amount)
    function startsTyping(e) { return forwardsTyping && !(e.modifiers & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier)) && /^[0-9.,+\-*\/=(]$/.test(e.text) }
    Keys.onShortcutOverride: (e) => { if (startsTyping(e)) e.accepted = true }    // a typed digit is the row's, never a window key
    Keys.onPressed: (e) => { if (startsTyping(e)) { s.typed(e.text); e.accepted = true } }
    Keys.onLeftPressed: (e) => nudge(-1, e.modifiers)
    Keys.onRightPressed: (e) => nudge(1, e.modifiers)
    property bool byPointer: false                   // the keyboard came with a press, not by Tab
    property int tabMoves: 0                         // the panel's scroll count when it got the keyboard (WheelLatch)
    onActiveFocusChanged: { if (activeFocus) tabMoves = WheelLatch.moves; else byPointer = false }
    WheelHandler {
        enabled: s.activeFocus && !s.byPointer && s.tabMoves === WheelLatch.moves
        acceptedModifiers: Qt.KeyboardModifierMask   // any: NoModifier is 0, so "None | Shift | Alt" meant Shift+Alt only (S36)
        onWheel: (e) => s.nudge((e.angleDelta.y || e.angleDelta.x) / 120, e.modifiers)
    }

    Component.onDestruction: if (drag.pressed) scrubEnded()   // a slider rebuilt under the pointer still closes its gesture

    HoverHandler { id: hoverHandler }
    Rectangle {  // track
        id: track
        anchors.verticalCenter: parent.verticalCenter
        x: knob.width / 2; width: parent.width - knob.width; height: 4; radius: 2
        color: s.hovered ? Theme.fg3 : Theme.lineHover      // a track you can see at 0 %, not a lone knob
        Behavior on color { ColorAnimation { duration: Theme.fast } }
        Rectangle { x: parent.width * Math.min(s.ratio, s.originRatio); width: parent.width * Math.abs(s.ratio - s.originRatio)
                    height: parent.height; radius: 2; color: Theme.accent }
    }
    Rectangle {  // knob
        id: knob
        anchors.verticalCenter: parent.verticalCenter
        x: s.ratio * (s.width - width)
        width: 12; height: 12; radius: 6
        color: "white"
        border.width: s.activeFocus || drag.pressed ? 2 : 0; border.color: Theme.accent
        scale: drag.pressed ? 1.15 : s.hovered ? 1.08 : 1
        Behavior on scale { NumberAnimation { duration: Theme.fast } }
    }
    MouseArea {
        id: drag
        anchors.fill: parent
        preventStealing: true
        cursorShape: Qt.PointingHandCursor
        property real anchorX: 0              // where the current speed began (a key went down or up): its value and place
        property real anchorValue: 0
        property int mode: 0                  // 0 normal, 1 fine, 2 coarse
        function follow(m) {
            const now = m.modifiers & Qt.AltModifier ? 1 : m.modifiers & Qt.ShiftModifier ? 2 : 0
            if (now !== mode) { mode = now; anchorX = m.x; anchorValue = s.shown }
            const span = s.width - knob.width
            const lo = s.showRange[0], hi = s.showRange[1]
            const v = mode === 1 ? anchorValue + (m.x - anchorX) / span * (hi - lo) / 10 : lo + (hi - lo) * s.ratioAt(m.x)
            s.scrubbed(s.clamp(v, mode === 2 ? s.showStep * 10 : mode === 1 ? s.showStep / 10 : s.showStep))
        }
        // The second press of a double-click puts the knob back to `defaultValue`: it starts no scrub (a scrub ending after the
        // reset would write the pointer's value over it). The first press of the pair has already moved the knob; one undo.
        property real lastUp: 0
        property real lastX: -100
        property bool resetting: false
        readonly property bool hasDefault: s.defaultValue !== null && s.defaultValue !== undefined
        onPressed: (m) => {
            s.byPointer = true; s.forceActiveFocus()
            resetting = hasDefault && Date.now() - lastUp < Qt.styleHints.mouseDoubleClickInterval && Math.abs(m.x - lastX) < 5   // same spot, quickly
            if (resetting) return
            s.scrubStarted()
            mode = -1; follow(m)              // -1: the first move sets the mode; Alt on press doesn't jump to the pointer
        }
        onPositionChanged: (m) => { if (!resetting) follow(m) }
        onDoubleClicked: if (hasDefault) s.edited(Math.max(s.from, Math.min(s.to, Number(s.defaultValue))))
        // after a reset the pair is spent: a press right after it is a new drag, never a third "double-click"
        onReleased: (m) => { if (resetting) { resetting = false; lastUp = 0; return } lastUp = Date.now(); lastX = m.x; s.scrubEnded() }
        onCanceled: { if (resetting) resetting = false; else s.scrubEnded() }
    }
}
