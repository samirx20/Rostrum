import QtQuick
import RostrumCursors 1.0

// How the pointer moves the canvas's view (INTERACTION 1.12), over every tool: Ctrl+wheel and pinch zoom around the
// pointer, the wheel scrolls (Shift: sideways), Space held + drag pans (middle-drag: Stage's well, a DragHandler there,
// so this layer is never a click target of its own). Everything else passes straight through to the tools: the Space
// drag area is on only while Space is down (spaceKey, screen2d/spacekey.py), the rest take only their own gesture. `view`: the canvas's CanvasView (screen state only).
Item {
    id: vi
    required property var view

    MouseArea {  // Space held + drag
        anchors.fill: parent
        visible: spaceKey.held                  // there only while Space is down (else it is no click target at all)
        acceptedButtons: Qt.LeftButton | Qt.MiddleButton
        preventStealing: true
        CanvasCursor { anchors.fill: parent; kind: parent.pressed ? "hand-grab" : "hand" }     // the hand: moving the view, nothing else (CURSORS.md)
        property point last
        onPressed: (m) => { spaceKey.use(); last = Qt.point(m.x, m.y) }
        onPositionChanged: (m) => { vi.view.panBy(m.x - last.x, m.y - last.y); last = Qt.point(m.x, m.y) }
    }
    WheelHandler {
        target: null
        acceptedModifiers: Qt.KeyboardModifierMask
        onWheel: (w) => {
            if (w.modifiers & Qt.ControlModifier) {
                vi.view.zoomAt(vi.view.zoom * Math.pow(1.25, w.angleDelta.y / 120), point.position.x, point.position.y)
                return
            }
            const d = (w.pixelDelta.x || w.pixelDelta.y) ? w.pixelDelta : Qt.point(w.angleDelta.x / 2, w.angleDelta.y / 2)
            if (w.modifiers & Qt.ShiftModifier) vi.view.panBy(d.y || d.x, 0); else vi.view.panBy(d.x, d.y)
        }
    }
    PinchHandler {  // a touchpad or touch pinch
        target: null
        property real last: 1
        onActiveChanged: last = 1
        onActiveScaleChanged: { vi.view.zoomAt(vi.view.zoom * activeScale / last, centroid.position.x, centroid.position.y); last = activeScale }
    }
}
