import QtQuick
import QtQuick.Controls as QQC
import RostrumKit

// The shell of the material popups (MaterialPicker, MaterialsList, Edit mesh's face material): opens just under an
// anchor, its left edge on the anchor's, kept inside the window. Built on the kit's one popup (SmallPopup), so it is in
// OpenPopups: the window's one Esc closes it (wherever the keyboard is), a click outside closes it, and the window's
// other keys keep working while it is open (a plain Popup with its own Esc stopped every window shortcut). When its
// whole list doesn't fit under the anchor and there is more room above (a Material row low in a long settings panel),
// it opens upward instead, so the list is never squeezed to a sliver at the window's bottom. Still too tall: `fit` is
// the room it may use, so the content inside scrolls. `natural`: the content's whole height (set by each popup).
// openFrom(anchor).
SmallPopup {
    id: pop
    property Item anchorItem: null
    property real natural: 0
    property real anchorTop: 0          // the anchor's top in the window, measured each place() (a panel still laying
                                        // out moves the row after the popup opened; a stale value let it run off the edge)
    readonly property real below: parent ? parent.height - 2 * Theme.grid - (anchorItem ? anchorTop + anchorItem.height + Theme.grid : 0) : 400
    readonly property real above: anchorItem ? anchorTop - 2 * Theme.grid - Theme.grid : 0
    readonly property bool upward: natural > below && above > below
    readonly property real fit: upward ? above : below
    parent: QQC.Overlay.overlay
    padding: Theme.gap
    focus: true
    background: MenuBackground { radius: Theme.radiusPanel }
    enter: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.fast } }
    exit: Transition { NumberAnimation { property: "opacity"; from: 1; to: 0; duration: Theme.fast } }

    function openFrom(item) { anchorItem = item; settle(); place(); open(); Qt.callLater(place) }
    function place() {
        const ov = parent
        if (!ov || !anchorItem) return
        const p = anchorItem.mapToItem(ov, 0, 0)
        if (anchorTop !== p.y) anchorTop = p.y      // fit and the content's height follow; onHeightChanged places again
        x = Math.max(Theme.grid, Math.min(p.x, ov.width - width - Theme.grid))
        y = upward ? Math.max(Theme.grid, p.y - Theme.grid - height)
                   : Math.max(Theme.grid, Math.min(p.y + anchorItem.height + Theme.grid, ov.height - height - Theme.grid))
    }
    onHeightChanged: if (visible) place()
    onClosed: anchorItem = null
    Timer { interval: 100; repeat: true; running: pop.visible; onTriggered: pop.place() }   // the row may still move
}
