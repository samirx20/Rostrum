import QtQuick
import RostrumKit
import "Mods.js" as Mods

// Picking and moving the frame on the canvas (camera spec 4.4, issues 6, 9, 10; screen2d/frame_drag.py does the work).
// The outline never catches a click: the name tab does (a click picks the frame, a drag moves it). While the frame alone
// is picked: a drag anywhere inside it moves it (even over layers; a click without a drag still picks what is under the
// pointer), a corner square zooms it (outward = bigger box = zoom down; Alt: about the opposite corner) and the zone
// just outside a corner turns it (Shift: 15° steps). Everything is turned with the frame. One drag = one change.
// None of it while looking through the frame (the frame is the canvas's edge then; its settings panel still works).
// `world` is WorldFrame.qml (the box in well px, the tab); `stage` gives world px (Stage.inWell).
Item {
    id: fh
    required property Item world
    required property Item stage
    anchors.fill: parent
    readonly property bool on: !backend.playing && !world.through && backend.tool === "move" && !spaceKey.held && world.halfW > 0
    readonly property bool picked: backend.frameDrag.picked
    visible: on

    function at(item, m) { const q = item.mapToItem(fh, m.x, m.y); return fh.stage.inWell(q.x, q.y) }   // world px

    Item {  // the frame's box in well px, turned with it about its centre: the parts below sit in its own (upright) px
        id: box
        x: fh.world.centreX - fh.world.halfW; y: fh.world.centreY - fh.world.halfH
        width: 2 * fh.world.halfW; height: 2 * fh.world.halfH
        transform: Rotation { origin.x: box.width / 2; origin.y: box.height / 2; angle: fh.world.box.rot || 0 }

        // a press inside: moves the frame once it travels, else picks what is under it; the tab: picks, and moves on a drag
        component Mover: MouseArea {
            id: mover
            property bool tab: false
            preventStealing: true
            property bool going: false
            property bool tried: false          // the drag was asked for once (a locked frame refuses once, not per move)
            property point p0
            property point s0
            onPressed: (m) => { going = tried = false; s0 = Qt.point(m.x, m.y); p0 = fh.at(mover, m); if (tab) backend.frameDrag.pick() }
            onPositionChanged: (m) => {
                if (!tried && Math.abs(m.x - s0.x) + Math.abs(m.y - s0.y) >= 4) {
                    tried = true
                    going = backend.frameDrag.begin("move", p0.x, p0.y, 0)
                }
                if (!going) return
                const p = fh.at(mover, m)
                backend.snap.keys(Mods.ctrl(m), Mods.shift(m))          // Ctrl: no snapping, Shift: straight (snapper.py)
                backend.frameDrag.moveBy(p.x - p0.x, p.y - p0.y)
            }
            onReleased: (m) => {
                if (going) backend.frameDrag.end()
                else if (!tab && !tried) {                                         // a click: what the canvas's click would pick
                    const deep = Mods.ctrl(m), hit = backend.multi.target(p0.x, p0.y, deep ? "deep" : "click")
                    if (hit !== "" && Mods.shift(m)) backend.multi.toggle(hit)
                    else backend.multi.pick(p0.x, p0.y, deep ? "deep" : "click")
                }
                going = false
            }
            onCanceled: { if (going) backend.frameDrag.end(); going = false }
        }
        Mover { anchors.fill: parent; enabled: fh.picked }
        Mover {     // over the tab (WorldFrame.qml draws it on the top-left corner)
            tab: true
            x: 0; y: -fh.world.tab.height; width: fh.world.tab.width; height: fh.world.tab.height
            cursorShape: Qt.PointingHandCursor
        }

        // a corner's drag: zoom (the square) or turn (the zone just outside it)
        component CornerDrag: MouseArea {
            id: cd
            property string kind
            property int corner
            preventStealing: true
            property bool going: false
            onPressed: (m) => { const p = fh.at(cd, m); going = backend.frameDrag.begin(kind, p.x, p.y, corner) }
            onPositionChanged: (m) => {
                if (!going) return
                const p = fh.at(cd, m)
                if (kind === "zoom") backend.frameDrag.zoomTo(p.x, p.y, Mods.alt(m))
                else backend.frameDrag.turnTo(p.x, p.y, Mods.shift(m))
            }
            onReleased: { if (going) backend.frameDrag.end(); going = false }
            onCanceled: { if (going) backend.frameDrag.end(); going = false }
        }
        Repeater {      // the turn zones, under the squares
            model: [[-1, -1], [1, -1], [1, 1], [-1, 1]]      // always made, shown while picked: a pick remakes nothing
            delegate: CornerDrag {
                required property var modelData
                required property int index
                visible: fh.picked
                kind: "turn"; corner: index
                width: 28; height: 28
                x: (modelData[0] + 1) / 2 * box.width + modelData[0] * 11 - 14
                y: (modelData[1] + 1) / 2 * box.height + modelData[1] * 11 - 14
                cursorShape: pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor
            }
        }
        Repeater {      // the corner squares
            model: [[-1, -1], [1, -1], [1, 1], [-1, 1]]
            delegate: Rectangle {
                id: knob
                required property var modelData
                required property int index
                visible: fh.picked
                width: 9; height: 9; color: "white"; border.width: 1; border.color: Theme.accent
                x: (modelData[0] + 1) / 2 * box.width - width / 2; y: (modelData[1] + 1) / 2 * box.height - height / 2
                Rectangle { anchors.fill: parent; anchors.margins: -1; color: "transparent"; border.width: 1; border.color: Qt.rgba(0, 0, 0, 0.6) }   // the halo
                CornerDrag {
                    anchors.fill: parent; anchors.margins: -4
                    kind: "zoom"; corner: knob.index
                    cursorShape: ({"hor": Qt.SizeHorCursor, "ver": Qt.SizeVerCursor, "fdiag": Qt.SizeFDiagCursor,
                                   "bdiag": Qt.SizeBDiagCursor})[backend.resizeCursor(knob.modelData[0], knob.modelData[1], fh.world.box.rot || 0)]
                }
            }
        }
    }
}
