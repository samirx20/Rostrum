import QtQuick
import RostrumKit
import RostrumCursors 1.0

// The view tools (rail › Hand / Zoom): only while one is on. Hand (H): drag moves the view. Zoom (Z): a click zooms
// in one step around the pointer, Alt+click out. Screen state only (CanvasView.qml), never the document. Pointers
// (CURSORS.md): the open / closed hand; the magnifier with + (Alt held, mouse still: −).
MouseArea {
    id: tools
    property var view
    readonly property bool hand: backend.tool === "hand"
    enabled: hand || backend.tool === "zoom"
    visible: enabled            // off: out of the way (a disabled but shown full-canvas area wins the pointer over the canvas)
    CanvasCursor { id: pointer; visible: tools.enabled; kind: tools.hand ? (tools.pressed ? "hand-grab" : "hand") : pointer.altHeld ? "zoom-minus" : "zoom-plus" }
    property point was
    onPressed: (m) => was = Qt.point(m.x, m.y)
    onPositionChanged: (m) => { if (hand && pressed) { view.panBy(m.x - was.x, m.y - was.y); was = Qt.point(m.x, m.y) } }
    onClicked: (m) => {
        if (hand) return
        const out = m.modifiers & Qt.AltModifier, z = view.zoom
        const s = out ? view.steps.filter(x => x < z / 1.001) : view.steps.filter(x => x > z * 1.001)
        if (s.length) view.zoomAt(out ? s[s.length - 1] : s[0], m.x, m.y)
    }
}
