import QtQuick
import QtQuick.Controls as QQC
import "."

// A panel that opens beside a field, to its left (so the inspector stays visible), top edges together; on the right
// when there is no room on the left. It stays inside the window. Used by the colour and fill fields.
//   pop.openBeside(field)
QQC.Popup {
    id: pop
    property Item anchorItem: null
    parent: QQC.Overlay.overlay
    padding: Theme.pad
    focus: true
    closePolicy: QQC.Popup.CloseOnPressOutside | QQC.Popup.CloseOnEscape
    background: Rectangle { color: Theme.raised; radius: Theme.radiusPanel; border.color: Theme.popupEdge }
    enter: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.fast } }
    exit: Transition { NumberAnimation { property: "opacity"; from: 1; to: 0; duration: Theme.fast } }

    function openBeside(item) { anchorItem = item; place(); open() }
    function place() {
        const ov = parent
        if (!ov || !anchorItem) return
        const p = anchorItem.mapToItem(ov, 0, 0)
        let x0 = p.x - width - Theme.gap
        if (x0 < Theme.grid) x0 = p.x + anchorItem.width + Theme.gap
        x = Math.max(Theme.grid, Math.min(x0, ov.width - width - Theme.grid))
        y = Math.max(Theme.grid, Math.min(p.y, ov.height - height - Theme.grid))
    }
    onWidthChanged: if (visible) place()
    onHeightChanged: if (visible) place()
}
