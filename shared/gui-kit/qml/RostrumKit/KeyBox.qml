import QtQuick
import RostrumKit

// The box that picks keys on a timeline's rows (INTERACTION 1.3: a box picks what it touches), drawn from an empty
// part of a track or the gap under it (LayerTrack.qml calls the rows' boxStart / boxTo / boxEnd, which hand on to this). On release every
// key whose diamond lies inside it, on every row it crosses, is picked (backend.keys.box; Ctrl / Shift: added). Dragged
// past the rows' top or bottom, the rows scroll and the box grows with them.
// Lies in the rows' ListView (its content px, as the rows); `ruler`: the timeline's.
Rectangle {
    id: kb
    property ListView list
    property Item ruler
    property rect box: Qt.rect(0, 0, 0, 0)
    property bool boxing: false
    property point from
    function start(p) { from = p; box = Qt.rect(p.x, p.y, 0, 0); passed = ({}); boxing = true; note() }
    // The rows the box has passed: a list builds only the rows near its view (2D LayerRows.qml: a small cacheBuffer,
    // rows reused), so a row scrolled out is gone by the release. Each row seen while boxing is kept by its place
    // (where it lay and its keys; nothing above it changes size during a box), and the release reads those.
    property var passed: ({})
    function note() {
        for (let i = 0; i < list.count; i++) {
            const item = list.itemAtIndex(i)
            if (item && item.visible) passed[i] = { y: item.y, height: item.height, keys: item.modelData.keys }
        }
    }
    Connections { target: kb.boxing ? kb.list : null; function onContentYChanged() { kb.note() } }   // scrolled while boxing (the edge, the wheel)
    function to(p) {
        const v = list.mapFromItem(list.contentItem, p.x, p.y)
        last = Qt.point(v.x, v.y)
        speed = v.y < Theme.grid ? v.y - Theme.grid : v.y > list.height - Theme.grid ? v.y - list.height + Theme.grid : 0
        reach(p)
    }
    function reach(p) { box = Qt.rect(Math.min(p.x, from.x), Math.min(p.y, from.y), Math.abs(p.x - from.x), Math.abs(p.y - from.y)) }
    // Past the rows' top or bottom edge the rows scroll, the further the faster, and the box grows with them: a box
    // reaches rows that were off screen (critic 2d-r11: 48 keys on 50 rows, only the 24 on screen could be boxed).
    property point last                     // the pointer, in the list's own px
    property real speed: 0                  // px past the edge (− above): the scroll per tick follows it
    Timer {
        interval: 16; repeat: true; running: kb.boxing && kb.speed !== 0
        onTriggered: {
            const step = Math.max(-40, Math.min(40, kb.speed / 2 || 0)), y0 = kb.list.contentY
            kb.list.contentY = Math.max(kb.list.originY, Math.min(kb.list.originY + kb.list.contentHeight - kb.list.height, y0 + step))
            if (kb.list.contentY !== y0) kb.reach(kb.list.mapToItem(kb.list.contentItem, kb.last.x, kb.last.y))
        }
    }
    function end(how) {
        boxing = false
        if (how === "cancel") return
        note()
        const groups = []
        for (const i in passed) {                         // the rows as shown (the list's model may be a list model, not an array)
            const item = passed[i]
            if (item.y + item.height < box.y || item.y > box.y + box.height) continue
            for (const k of item.keys) {
                const x = ruler.x + ruler.xOf(k.t)
                if (x >= box.x - 4 && x <= box.x + box.width + 4) groups.push(k.ids || [k.id])
            }
        }
        passed = ({})
        backend.keys.box(groups, how)
    }
    parent: list ? list.contentItem : null          // drawn in the rows' own px, so it scrolls with them
    visible: boxing; z: 6
    x: box.x; y: box.y; width: box.width; height: box.height
    color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.12); border.color: Theme.accent; border.width: 1
}
