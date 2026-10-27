import QtQuick
import RostrumKit

// The time ruler's right-click menu and the work area band (backend.workArea, screen2d/work_area.py). Right-click on
// the ruler (not on a marker flag: a flag keeps its own menu): Add a marker here… (the ruler's name field at that
// time), Work area starts / ends here, Clear the work area, Go to here, Go to the start / end. The work area shows as
// the ruler's range band while there is one: drag it to change it, double-click it to clear it. A marker added at the
// playhead by the flag button or M opens its name field at once (backend.workArea.named).
Item {
    id: rm
    required property var ruler
    readonly property var wa: backend.workArea
    parent: ruler
    anchors.fill: parent

    Binding { target: rm.ruler; property: "rangeBand"; value: !!rm.wa.range }
    Binding { target: rm.ruler; property: "range"; value: rm.wa.range }
    Connections {
        target: rm.ruler
        function onRangeSet(a, b) { rm.wa.set(a, b) }
        function onRangeCleared() { rm.wa.clear() }
        function onMarkerAdded(name, shared, at) { rm.wa.addMarker(name, at) }
    }
    Connections {
        target: rm.wa
        function onNamed(id) {          // the new flag's own name field (MarkerFlag.startRename), once it is drawn
            Qt.callLater(() => { for (const c of rm.ruler.children)
                                     if (c.modelData && c.modelData.id === id && c.startRename) { c.startRename(); return } })
        }
    }
    function onFlag(x, y) {             // a marker flag is under the pointer: its own menu, not this one
        if (y > rm.ruler.flagTop + 18) return false
        for (const m of rm.ruler.markers) if (Math.abs(rm.ruler.xOfSec(m.at) - x) < 10) return true
        return false
    }
    MouseArea {
        objectName: "rulerMenuArea"
        anchors.fill: parent
        acceptedButtons: Qt.RightButton
        onPressed: (m) => { m.accepted = !rm.onFlag(m.x, m.y) }
        onClicked: (m) => {
            menu.sec = rm.ruler.secOf(m.x)
            menu.entries = rm.wa.menu(menu.sec)
            const g = mapToItem(null, m.x, m.y)
            menu.openAt(g.x, g.y)
        }
    }
    ActionMenu {
        id: menu
        objectName: "rulerMenu"
        property real sec: 0
        onPicked: (v) => {
            if (v === "marker") { backend.setTime(sec); rm.ruler.newMarker() }
            else rm.wa.choose(v, sec)
        }
    }
}
