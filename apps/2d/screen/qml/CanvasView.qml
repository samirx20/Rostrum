import QtQuick

// The canvas's view: how big the frame is shown (`zoom`, screen px per composition px) and where (`ox`, `oy`: where
// composition (0, 0) sits in the well). Screen state only: never the document, no undo step, an agent never moves it.
// Stage.qml turns this into its one mapping (compScale, compOrigin, toComp, fromComp); nothing else reads it directly
// except Stage's own children and the view controls. `fitted`: the frame fills the well (follows the window's size);
// any zoom or pan holds the view where it is (`asked` zoom, the composition point `cx`, `cy` at the well's centre).
QtObject {
    id: v
    property real wellW: 0
    property real wellH: 0
    property real compW: 1
    property real compH: 1
    property real top: 0                       // room kept clear above the frame at Fit, for the context bar (Stage.qml)
    readonly property real margin: 24
    readonly property real fitMost: 4          // F on a tiny layer stops at 400 % (the frame is drawn at most at Full)
    readonly property real above: Math.max(margin, top)   // the bar's room counts as the top margin, not on top of it
    readonly property real fit: Math.max(0.01, Math.min((wellW - 2 * margin) / compW, (wellH - above - margin) / compH))
    property bool fitted: true
    property real asked: 1
    property real cx: 0
    property real cy: 0
    readonly property real zoom: fitted ? fit : asked
    readonly property real ox: Math.round(wellW / 2 - (fitted ? compW / 2 : cx) * zoom)
    readonly property real oy: Math.round(fitted ? above + (wellH - above - margin - compH * zoom) / 2 : wellH / 2 - cy * zoom)
    readonly property var steps: [0.02, 0.05, 0.1, 0.125, 0.25, 1 / 3, 0.5, 2 / 3, 1, 1.5, 2, 3, 4, 6, 8, 12, 16, 32, 64]

    function clamp(z) { return Math.max(steps[0], Math.min(steps[steps.length - 1], z)) }
    function hold() { if (fitted) { asked = fit; cx = compW / 2; cy = compH / 2; fitted = false } }
    function fitAll() { fitted = true }
    // zoom to `z`, keeping the composition point under (px, py) (well px) where it is
    function zoomAt(z, px, py) {
        const ax = (px - ox) / zoom, ay = (py - oy) / zoom
        hold()
        asked = clamp(z)
        cx = ax - (px - wellW / 2) / asked; cy = ay - (py - wellH / 2) / asked
    }
    function show(z) { zoomAt(z, wellW / 2, wellH / 2) }                       // keeps the centre
    function centreOn(x, y) { hold(); cx = x; cy = y }                           // composition px
    function panBy(dx, dy) { hold(); cx -= dx / zoom; cy -= dy / zoom }          // screen px
    function fitBox(x0, y0, x1, y1) {                                            // composition px
        const w = Math.max(x1 - x0, 1), h = Math.max(y1 - y0, 1)
        hold()
        asked = clamp(Math.min((wellW - 2 * margin) / w, (wellH - 2 * margin) / h, fitMost))
        cx = (x0 + x1) / 2; cy = (y0 + y1) / 2
    }
    function step(dir) {                                                        // Ctrl+= / Ctrl+−: the next step
        const up = steps.filter(s => s > zoom * 1.001), down = steps.filter(s => s < zoom / 1.001)
        show(dir > 0 ? (up.length ? up[0] : zoom) : (down.length ? down[down.length - 1] : zoom))
    }
}
