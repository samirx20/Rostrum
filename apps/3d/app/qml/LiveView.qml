import QtQuick
import Rostrum3DView

// The live view drawn inside the window (Viewport.qml loads it when viewport.inWindow): the engine's own core draws
// the scene straight into this item (apps/3d/core/view/viewport_item.h); requests and replies go through
// viewport.viewLink (screen3d/view_item.py). Input stays with the Viewport's layers above it.
Rostrum3DView {
    id: live
    objectName: "liveView3d"
    onAnswered: (n, reply) => viewport.viewLink.answered(n, reply)
    onDrawn: (reply) => viewport.viewLink.onDrawn(reply)
    onFrameShown: (frame, t) => viewport.viewLink.onShown(frame, t)
    Component.onCompleted: viewport.viewLink.attach(live)
}
