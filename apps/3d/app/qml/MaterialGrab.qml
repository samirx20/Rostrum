import QtQuick
import QtQuick.Controls as QQC
import RostrumKit

// The click-or-drag surface of a material row or tile (SPEC 6.1). Fills its parent. A click sends clicked(). With a
// `materialId`, dragging it picks up a small ball (mime "application/x-rostrum-material", key "rostrum-material",
// and `materialId` on the dragged item) that a DropArea in the scene list or the viewport takes: the item under it gets
// that material. A start (no id) is click only. dragEnded() tells the popup around it to close.
MouseArea {
    id: grab
    property string materialId: ""
    property color colour: Theme.raised
    property url ball: ""
    signal dragEnded()
    anchors.fill: parent
    hoverEnabled: true; cursorShape: Qt.PointingHandCursor
    drag.target: materialId !== "" ? ghost : null
    drag.threshold: Theme.gap
    onPressed: (m) => { const p = mapToItem(ghost.parent, m.x, m.y); ghost.x = p.x - ghost.width / 2; ghost.y = p.y - ghost.height / 2 }
    onReleased: if (drag.active) { ghost.Drag.drop(); grab.dragEnded() }

    Ball {          // the ball under the pointer while dragging (in the window's top layer: no panel clips it)
        id: ghost
        readonly property string materialId: grab.materialId     // what a DropArea reads: drag.source.materialId
        parent: QQC.Overlay.overlay
        size: Theme.row; colour: grab.colour; source: grab.ball
        visible: Drag.active; opacity: 0.9
        Drag.active: grab.drag.active
        Drag.source: ghost
        Drag.keys: ["rostrum-material"]
        Drag.mimeData: { "application/x-rostrum-material": grab.materialId }
        Drag.hotSpot: Qt.point(width / 2, height / 2)
    }
}
