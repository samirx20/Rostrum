import QtQuick
import "."

// A slider. Pressing on it jumps there and dragging follows: the whole press-to-release is one gesture
// (scrubStarted, scrubbed(value)…, scrubEnded), recorded by the app as ONE change. Left / Right step: edited(value).
Item {
    id: s
    property real value: 0
    property real from: 0
    property real to: 1
    property real step: 0.01
    readonly property bool hovered: hoverHandler.hovered
    readonly property bool pressed: drag.pressed
    readonly property real ratio: to > from ? (Math.max(from, Math.min(to, value)) - from) / (to - from) : 0
    signal edited(real value)
    signal scrubStarted()
    signal scrubbed(real value)
    signal scrubEnded()
    implicitWidth: 140; implicitHeight: Theme.field
    activeFocusOnTab: true

    function clamp(v) { return Math.max(from, Math.min(to, Math.round((v - from) / step) * step + from)) }
    function at(x) { return clamp(from + (to - from) * Math.max(0, Math.min(1, (x - knob.width / 2) / (width - knob.width)))) }
    Keys.onLeftPressed: edited(clamp(value - step))
    Keys.onRightPressed: edited(clamp(value + step))

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
        onPressed: (m) => { s.forceActiveFocus(); s.scrubStarted(); s.scrubbed(s.at(m.x)) }
        onPositionChanged: (m) => s.scrubbed(s.at(m.x))
        onReleased: s.scrubEnded()
        onCanceled: s.scrubEnded()
    }
}
