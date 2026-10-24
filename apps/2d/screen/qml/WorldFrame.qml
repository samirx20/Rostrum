import QtQuick
import QtQuick.Shapes
import RostrumKit

// The frame's marks on the canvas (SPEC 2d-camera 3.1, 4.2): the dimmed outside (black, 55 %), the outline (1 px, turned
// with the frame) and the name tab over its top-left corner. All of it is plain shapes bound to a few numbers (the box:
// backend.frameView.box, in world px, and the view's mapping), so panning and zooming cost no Python. The selection's
// marks come later in Stage.qml and so stay above the dimming at full strength. Hidden while playing: the canvas then
// shows the export itself. Picked (backend.frameDrag.picked: C, the tab, the Frame row) the outline and tab turn accent
// blue; its handles and drags are FrameHandles.qml, which reads `corners` and `tab` from here. `edge` / `along` tell FrameChip.qml where the frame lies when it is entirely out of
// view (that chip sits above the canvas's mouse area, so it is a separate item). Looking through the frame (`through`,
// LookThrough.qml): the outside is covered in the well colour and there is no outline and no tab.
Item {
    id: root
    required property var view
    property bool through: false
    anchors.fill: parent
    visible: !backend.playing

    readonly property var box: backend.frameView.box
    readonly property bool picked: backend.frameDrag.picked
    readonly property alias tab: tab
    readonly property real zoom: view.zoom
    readonly property real centreX: view.ox + (box.cx || 0) * zoom      // the frame's centre, in well px
    readonly property real centreY: view.oy + (box.cy || 0) * zoom
    readonly property real halfW: (box.w || 0) * zoom / 2
    readonly property real halfH: (box.h || 0) * zoom / 2
    readonly property real turn: (box.rot || 0) * Math.PI / 180
    // the four corners in well px: top-left, top-right, bottom-right, bottom-left (turning clockwise: y points down)
    readonly property var corners: {
        const c = Math.cos(turn), s = Math.sin(turn), out = []
        for (const k of [[-1, -1], [1, -1], [1, 1], [-1, 1]]) {
            const x = k[0] * halfW, y = k[1] * halfH
            out.push(Qt.point(centreX + c * x - s * y, centreY + s * x + c * y))
        }
        return out
    }
    readonly property real x0: Math.min(corners[0].x, corners[1].x, corners[2].x, corners[3].x)
    readonly property real x1: Math.max(corners[0].x, corners[1].x, corners[2].x, corners[3].x)
    readonly property real y0: Math.min(corners[0].y, corners[1].y, corners[2].y, corners[3].y)
    readonly property real y1: Math.max(corners[0].y, corners[1].y, corners[2].y, corners[3].y)
    // entirely outside the visible well: which way it lies ("left", "right", "top", "bottom"), the larger gap deciding
    readonly property string edge: {
        const gl = -x1, gr = x0 - width, gt = -y1, gb = y0 - height
        const g = Math.max(gl, gr, gt, gb)
        if (g <= 0) return ""
        return g === gl ? "left" : g === gr ? "right" : g === gt ? "top" : "bottom"
    }
    readonly property real along: edge === "left" || edge === "right" ? centreY : centreX   // where on that edge the chip sits

    function point(p) { return p.x + "," + p.y }
    // (x, y) in well px lies inside the frame's quad
    function inside(x, y) {
        const dx = x - centreX, dy = y - centreY, c = Math.cos(turn), s = Math.sin(turn)
        return Math.abs(c * dx + s * dy) <= halfW && Math.abs(-s * dx + c * dy) <= halfH
    }
    Shape {  // the veil: the whole well (its rounded corners kept) minus the frame's quad (odd-even fill)
        anchors.fill: parent
        ShapePath {
            strokeWidth: -1; fillColor: root.through ? Theme.sunken : Qt.rgba(0, 0, 0, 0.55); fillRule: ShapePath.OddEvenFill
            PathSvg {
                path: {
                    const r = Theme.radiusCtl, w = root.width, h = root.height, a = " A" + r + "," + r + " 0 0 1 "
                    return "M" + r + ",0 H" + (w - r) + a + w + "," + r + " V" + (h - r) + a + (w - r) + "," + h
                           + " H" + r + a + "0," + (h - r) + " V" + r + a + r + ",0 Z M" + root.point(root.corners[0])
                           + " L" + root.point(root.corners[1]) + " L" + root.point(root.corners[2])
                           + " L" + root.point(root.corners[3]) + " Z"
                }
            }
        }
    }
    Shape {  // the outline
        anchors.fill: parent
        visible: !root.through
        ShapePath {
            strokeWidth: root.picked ? 1.5 : 1; strokeColor: root.picked ? Theme.accent : Qt.alpha(Theme.fg, 0.7)
            fillColor: "transparent"; joinStyle: ShapePath.MiterJoin
            PathSvg {
                path: "M" + root.point(root.corners[0]) + " L" + root.point(root.corners[1]) + " L" + root.point(root.corners[2])
                      + " L" + root.point(root.corners[3]) + " Z"
            }
        }
    }
    Rectangle {  // the name tab: sits on the outline's top-left corner, turned with the frame; a click picks the frame (FrameHandles.qml)
        id: tab
        visible: !root.through
        width: words.width + 2 * Theme.gap; height: words.height + 4
        radius: Theme.radiusCtl; color: root.picked ? Theme.accent : Theme.raised
        x: root.corners[0].x; y: root.corners[0].y - height
        transformOrigin: Item.BottomLeft; rotation: box.rot || 0
        Text { id: words; anchors.centerIn: parent; text: backend.frameView.label; color: root.picked ? "white" : Theme.fg2
               font.family: uiFont; font.pixelSize: Theme.label }
    }
}
