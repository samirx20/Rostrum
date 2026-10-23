import QtQuick
import RostrumKit

// The view tools (rail › Hand / Zoom): only while one is on. Hand (H): drag moves the view. Zoom (Z): a click zooms
// in one step around the pointer, Alt+click out. Screen state only (CanvasView.qml), never the document.
MouseArea {
    id: tools
    property var view
    readonly property bool hand: backend.tool === "hand"
    enabled: hand || backend.tool === "zoom"
    cursorShape: hand ? (pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor) : Qt.CrossCursor
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
