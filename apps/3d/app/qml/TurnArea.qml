import QtQuick

// The viewport's right button (Viewport.qml): a right drag turns the view (`turned`, each move in screen px, in every
// tool), a right click (pressed and let go within 3 px) is `rightClicked` where it was pressed (the menu there).
MouseArea {
    id: ta
    signal turned(real dx, real dy)
    signal rightClicked(real x, real y)
    acceptedButtons: Qt.RightButton
    preventStealing: true
    property real px: 0
    property real py: 0
    property real lx: 0
    property real ly: 0
    property bool dragged: false
    onPressed: (m) => { px = lx = m.x; py = ly = m.y; dragged = false }
    onPositionChanged: (m) => {
        dragged = dragged || Math.abs(m.x - px) + Math.abs(m.y - py) > 3
        if (!dragged) return
        ta.turned(m.x - lx, m.y - ly)
        lx = m.x; ly = m.y
    }
    onReleased: (m) => { if (!dragged) ta.rightClicked(px, py) }
}
