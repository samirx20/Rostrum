import QtQuick
import QtQuick.Controls as QQC
import RostrumKit

// The shell of the material popups (MaterialPicker, MaterialsList, Edit mesh's face material): opens just under an
// anchor, its left edge on the anchor's, kept inside the window. Built on the kit's one popup (SmallPopup), so it is in
// OpenPopups: the window's one Esc closes it (wherever the keyboard is), a click outside closes it, and the window's
// other keys keep working while it is open (a plain Popup with its own Esc stopped every window shortcut). Too tall for
// the window: `fit` is the room it may use, so the content inside scrolls instead. openFrom(anchor).
SmallPopup {
    id: pop
    property Item anchorItem: null
    readonly property real fit: parent ? parent.height - 2 * Theme.grid - (anchorItem ? anchorItem.mapToItem(parent, 0, 0).y + anchorItem.height + Theme.grid : 0) : 400
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
        x = Math.max(Theme.grid, Math.min(p.x, ov.width - width - Theme.grid))
        y = Math.max(Theme.grid, Math.min(p.y + anchorItem.height + Theme.grid, ov.height - height - Theme.grid))
    }
    onHeightChanged: if (visible) place()
    onClosed: anchorItem = null
}
