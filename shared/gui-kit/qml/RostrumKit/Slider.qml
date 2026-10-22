import QtQuick
import "."

// A slider. Pressing on it jumps there and dragging follows: the whole press-to-release is one gesture
// (scrubStarted, scrubbed(value)…, scrubEnded), recorded by the app as ONE change. Left / Right step: edited(value).
// Keys held while dragging: Alt = fine (the drag moves the value at a tenth of the speed, from where Alt went down; no
// jump on press), Shift = coarse (the value lands on every 10th step). Same for Left / Right and the wheel.
// Double-click puts it back to `defaultValue` (edited(default); none set: nothing happens). The wheel changes it only
// while it has keyboard focus, so the panel scrolls past it otherwise.
Item {
    id: s
    property real value: 0
    property real from: 0
    property real to: 1
    property real step: 0.01
    property var defaultValue: null                  // the setting's own default; null = none (no reset)
    readonly property bool hovered: hoverHandler.hovered
    readonly property bool pressed: drag.pressed
    readonly property real ratio: to > from ? (Math.max(from, Math.min(to, value)) - from) / (to - from) : 0
    signal edited(real value)
    signal scrubStarted()
    signal scrubbed(real value)
    signal scrubEnded()
    implicitWidth: 140; implicitHeight: Theme.field
    activeFocusOnTab: true

    function clamp(v, unit) { const u = unit || step; return Math.max(from, Math.min(to, Math.round((v - from) / u) * u + from)) }
    function ratioAt(x) { return Math.max(0, Math.min(1, (x - knob.width / 2) / (width - knob.width))) }
    function unitFor(mods) { return mods & Qt.AltModifier ? step / 10 : mods & Qt.ShiftModifier ? step * 10 : step }
    function nudge(n, mods) { const u = unitFor(mods); edited(clamp(value + n * u, u)) }
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
        color: s.hovered ? Theme.lineHover : Theme.active
        Behavior on color { ColorAnimation { duration: Theme.fast } }
        Rectangle { width: parent.width * s.ratio; height: parent.height; radius: 2; color: Theme.accent }
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
            if (now !== mode) { mode = now; anchorX = m.x; anchorValue = s.value }
            const span = s.width - knob.width
            const v = mode === 1 ? anchorValue + (m.x - anchorX) / span * (s.to - s.from) / 10
                    : s.from + (s.to - s.from) * s.ratioAt(m.x)
            s.scrubbed(s.clamp(v, mode === 2 ? s.step * 10 : mode === 1 ? s.step / 10 : s.step))
        }
        onPressed: (m) => {
            s.forceActiveFocus(); s.scrubStarted()
            mode = -1; follow(m)              // -1: the first move sets the mode; Alt on press doesn't jump to the pointer
        }
        onPositionChanged: (m) => follow(m)
        onDoubleClicked: if (s.defaultValue !== null && s.defaultValue !== undefined) s.edited(s.clamp(Number(s.defaultValue)))
        onReleased: s.scrubEnded()
        onCanceled: s.scrubEnded()
    }
}
