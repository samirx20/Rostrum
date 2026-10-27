import QtQuick
import "."

// The wheel scrolls a Flickable (a panel, a list) by moving it at once, never as a flick. Flickable's own wheel left it
// "moving" for ~0.75 s after the last notch, and a press while it moves only stops it: the first click after a scroll
// was eaten ("+ Add an effect" at the panel's end showed only its tooltip, × left the effect; critic 2d-final row 9).
// Put one inside the Flickable: WheelScroll { flick: scroller }. A child that takes the wheel itself (a number box with
// the caret in it) still gets it first.
WheelHandler {
    property Flickable flick
    parent: flick
    target: null
    acceptedModifiers: Qt.NoModifier
    onWheel: (e) => {
        const f = flick
        if (!f || !f.interactive) { e.accepted = false; return }
        const dy = e.pixelDelta.y !== 0 ? e.pixelDelta.y : e.angleDelta.y / 120 * 3 * Theme.row      // a notch: three rows
        const top = f.originY, bottom = f.originY + Math.max(0, f.contentHeight - f.height)
        const y = Math.max(top, Math.min(bottom, f.contentY - dy))
        if (y === f.contentY && dy !== 0) { e.accepted = false; return }      // at its end: the wheel is the next one's
        f.cancelFlick()
        f.contentY = y
    }
}
