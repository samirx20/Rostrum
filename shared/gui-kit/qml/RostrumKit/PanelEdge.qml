import QtQuick
import "."

// A panel's edge you can drag (AppShell's frame layout): `moved(d)` with the pointer's travel since the press
// (px, + = right / down), `reset()` on a double-click (the size goes back to the automatic layout).
// `vertical`: a left / right edge (resizes width), else a top / bottom edge.
MouseArea {
    id: edge
    property bool vertical: true
    signal moved(real d)
    signal reset()
    hoverEnabled: true
    cursorShape: vertical ? Qt.SizeHorCursor : Qt.SizeVerCursor
    property real start: 0
    property real last: 0
    onPressed: (e) => { start = vertical ? mapToItem(null, e.x, 0).x : mapToItem(null, 0, e.y).y; last = 0 }
    onPositionChanged: (e) => {
        if (!pressed) return
        const now = (vertical ? mapToItem(null, e.x, 0).x : mapToItem(null, 0, e.y).y) - start
        edge.moved(now - last); last = now
    }
    onDoubleClicked: edge.reset()
    Rectangle { anchors.centerIn: parent; width: edge.vertical ? 2 : parent.width; height: edge.vertical ? parent.height : 2
                color: Theme.accent; opacity: edge.containsMouse || edge.pressed ? 0.6 : 0
                Behavior on opacity { NumberAnimation { duration: Theme.fast } } }
}
