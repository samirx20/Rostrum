import QtQuick
import "."
import "ValueKinds.js" as VK

// A slider. Pressing on it jumps there and dragging follows: the whole press-to-release is one gesture
// (scrubStarted, scrubbed(value)…, scrubEnded), recorded by the app as ONE change. Left / Right step: edited(value).
// Keys held while dragging: Alt = fine (the drag moves the value at a tenth of the speed, from where Alt went down; no
// jump on press), Shift = coarse (the value lands on every 10th step). Same for Left / Right and the wheel.
// Double-click puts it back to `defaultValue` (edited(default); none set: nothing happens). The wheel changes it only
// while it has keyboard focus, so the panel scrolls past it otherwise.
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

    function clamp(n, unit) {                        // a shown number -> the stored value, in range
        const u = unit || showStep
        const k = Math.max(showRange[0], Math.min(showRange[1], Math.round((n - showRange[0]) / u) * u + showRange[0]))
        return Math.max(from, Math.min(to, VK.stored(display, k)))
    }
    function ratioAt(x) { return Math.max(0, Math.min(1, (x - knob.width / 2) / (width - knob.width))) }
    function unitFor(mods) { return mods & Qt.AltModifier ? showStep / 10 : mods & Qt.ShiftModifier ? showStep * 10 : showStep }
    function nudge(n, mods) { const u = unitFor(mods); edited(clamp(shown + n * u, u)) }
    Keys.onLeftPressed: (e) => nudge(-1, e.modifiers)
    Keys.onRightPressed: (e) => nudge(1, e.modifiers)
    WheelHandler {
        enabled: s.activeFocus
        acceptedModifiers: Qt.KeyboardModifierMask   // any: NoModifier is 0, so "None | Shift | Alt" meant Shift+Alt only (S36)
        onWheel: (e) => s.nudge((e.angleDelta.y || e.angleDelta.x) / 120, e.modifiers)
    }

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
        onPressed: (m) => {
            s.forceActiveFocus(); s.scrubStarted()
            mode = -1; follow(m)              // -1: the first move sets the mode; Alt on press doesn't jump to the pointer
        }
        onPositionChanged: (m) => follow(m)
        onDoubleClicked: if (s.defaultValue !== null && s.defaultValue !== undefined) s.edited(Math.max(s.from, Math.min(s.to, Number(s.defaultValue))))
        onReleased: s.scrubEnded()
        onCanceled: s.scrubEnded()
    }
}
