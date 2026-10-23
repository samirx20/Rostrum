import QtQuick

// The short slide of the canvas's picture to a camera's new view (about 150 ms, ease out) after a camera key is dropped.
// The picture is re-drawn through the new camera; instead of jumping, the old picture is held, scaled and moved so that
// the new camera's box (backend.viewGlide, composition px as seen) fills the frame, and the new picture takes over at the
// end (it looks the same there). The view only: no document change, no undo step, never in the export.
// `shown` is the picture serial to draw; `sx sy tx ty` the transform of the frame item (frame px).
QtObject {
    id: g
    property int serial: 0                  // the live picture (backend.frame)
    property real zoom: 1                   // screen px per composition px
    property int shown: serial
    property var box: null                  // [x0, y0, x1, y1] waiting for the new picture
    property real p: 0
    readonly property bool running: anim.running
    readonly property real kx: box ? Math.max(0.05, Math.min(20, width / (box[2] - box[0]))) : 1
    readonly property real ky: box ? Math.max(0.05, Math.min(20, height / (box[3] - box[1]))) : 1
    property real width: 1                  // the frame in composition px
    property real height: 1
    readonly property real sx: 1 + (kx - 1) * p
    readonly property real sy: 1 + (ky - 1) * p
    readonly property real tx: box ? -box[0] * zoom * kx * p : 0
    readonly property real ty: box ? -box[1] * zoom * ky * p : 0
    property bool pending: false

    onSerialChanged: {
        if (pending && box && !anim.running) { pending = false; anim.restart() }   // the new picture is here: slide to it
        else if (!anim.running) shown = serial                                     // else: it follows the live picture
    }
    property Connections link: Connections {
        target: backend
        function onViewGlide(b) { g.box = b; g.pending = true }
    }
    property NumberAnimation anim: NumberAnimation {
        target: g; property: "p"; from: 0; to: 1; duration: 150; easing.type: Easing.OutCubic
        onFinished: { g.shown = g.serial; g.box = null; g.p = 0 }
    }
}
