import QtQuick
import QtQuick.Controls as QQC
import "."

// A panel that opens beside a field, top edges together with the field's. Inside a panel that keeps popups beside it
// (`popupsBeside: true`, the settings panel) it opens to the LEFT of that whole panel, so no label or field is covered;
// on its right when there is no room on the left; when neither fits it is clamped into the window. Elsewhere it opens
// beside the field itself. It stays inside the window. Used by the colour and fill fields.
//   pop.openBeside(field)
SmallPopup {
    id: pop
    property Item anchorItem: null
    parent: QQC.Overlay.overlay
    padding: Theme.pad
    focus: true
    background: MenuBackground { radius: Theme.radiusPanel }
    enter: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.fast } }
    exit: Transition { NumberAnimation { property: "opacity"; from: 1; to: 0; duration: Theme.fast } }

    function openBeside(item) { anchorItem = item; place(); open() }
    function place() {
        settle()
        const ov = parent
        if (!ov || !anchorItem) return
        const p = anchorItem.mapToItem(ov, 0, 0)
        let side = anchorItem
        for (let it = anchorItem.parent; it; it = it.parent) if (it.popupsBeside === true) { side = it; break }
        const s = side.mapToItem(ov, 0, 0)
        let x0 = s.x - width - Theme.gap
        if (x0 < Theme.grid) x0 = s.x + side.width + Theme.gap
        x = Math.max(Theme.grid, Math.min(x0, ov.width - width - Theme.grid))
        y = Math.max(Theme.grid, Math.min(p.y, ov.height - height - Theme.grid))
    }
}
