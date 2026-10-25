import QtQuick
import RostrumKit

// The box that picks keys on a timeline's rows (INTERACTION 1.3: a box picks what it touches), drawn from an empty
// part of a track or the gap under it (LayerTrack.qml calls the rows' boxStart / boxTo / boxEnd, which hand on to this). On release every
// key whose diamond lies inside it, on every row it crosses, is picked (backend.keys.box; Ctrl / Shift: added).
// Lies in the rows' ListView (its content px, as the rows); `ruler`: the timeline's.
Rectangle {
    id: kb
    property ListView list
    property Item ruler
    property rect box: Qt.rect(0, 0, 0, 0)
    property bool boxing: false
    property point from
    function start(p) { from = p; box = Qt.rect(p.x, p.y, 0, 0); boxing = true }
    function to(p) { box = Qt.rect(Math.min(p.x, from.x), Math.min(p.y, from.y), Math.abs(p.x - from.x), Math.abs(p.y - from.y)) }
    function end(how) {
        boxing = false
        if (how === "cancel") return
        const groups = []
        for (let i = 0; i < list.count; i++) {            // the rows as shown (the list's model may be a list model, not an array)
            const item = list.itemAtIndex(i)
            if (!item || item.y + item.height < box.y || item.y > box.y + box.height) continue
            for (const k of item.modelData.keys) {
                const x = ruler.x + ruler.xOf(k.t)
                if (x >= box.x - 4 && x <= box.x + box.width + 4) groups.push(k.ids || [k.id])
            }
        }
        backend.keys.box(groups, how)
    }
    visible: boxing; z: 6
    x: box.x; y: box.y; width: box.width; height: box.height
    color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.12); border.color: Theme.accent; border.width: 1
}
