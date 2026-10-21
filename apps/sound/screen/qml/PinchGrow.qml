import QtQuick

// A pinch over a timeline zooms it around the fingers (backend.zoomAt: the scale since the last step, and
// where across the width the fingers are). Put it inside the item that takes the clicks.
PinchHandler {
    id: pinch
    property real last: 1
    target: null
    onActiveChanged: last = 1
    onActiveScaleChanged: {
        if (!active) return
        backend.zoomAt(activeScale / last, centroid.position.x / Math.max(1, parent.width))
        last = activeScale
    }
}
