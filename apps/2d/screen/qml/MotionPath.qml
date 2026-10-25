import QtQuick
import RostrumKit
import "Mods.js" as Mods

// The motion path over the canvas (screen2d/motion_path.py does the work): where the selected layer travels, a dot per
// frame (close dots: slow, far apart: fast), a square per key (filled when picked) and the picked or bent keys' handles;
// a jump (for the frame, a cut) is a dashed line with no dots; for the frame, a faint outline of it at each key. Drag a
// square: the key moves, snapping as a layer does (Ctrl or Alt: free); drag a handle end: the path bends, the opposite
// handle mirrored (Alt: not). One drag = one change. Hidden while playing. Positions come in world px; fit / ox / oy are
// the Stage's one mapping (canvas px = o + world px × fit), so a pan or zoom only repaints. `noFrame`: the frame's own
// path left out (looking through the frame: it is the canvas's edge then).
Item {
    id: mp
    property real fit: 1
    property real ox: 0
    property real oy: 0
    property bool interactive: true
    property bool noFrame: false
    readonly property var paths: noFrame ? backend.motionPath.paths.filter(r => !r.frame) : backend.motionPath.paths
    readonly property int hit: 18               // the invisible click target round a square or a handle end (≥ the kit's 16)
    function cx(p) { return mp.ox + p[0] * mp.fit }
    function cy(p) { return mp.oy + p[1] * mp.fit }

    Canvas {
        id: ink
        anchors.fill: parent
        onPaint: {
            const g = getContext("2d")
            g.reset()
            const a = Theme.accent
            for (const row of mp.paths) {
                const ac = Qt.rgba(a.r, a.g, a.b, row.faint ? 0.35 : 0.7)
                g.lineWidth = 1
                g.strokeStyle = Qt.rgba(a.r, a.g, a.b, row.faint ? 0.18 : 0.4)
                for (const f of row.frames) poly(g, f, true)                   // the frame at each of its keys
                g.strokeStyle = ac
                for (const line of row.lines) poly(g, line, false)
                g.setLineDash([4, 4])                                          // a jump: nothing travels there
                for (const c of row.cuts) poly(g, c, false)
                g.setLineDash([])
                g.fillStyle = ac
                for (const p of row.ticks) { g.beginPath(); g.arc(mp.cx(p), mp.cy(p), row.faint ? 1.2 : 1.6, 0, 2 * Math.PI); g.fill() }
                for (const k of row.keys) {
                    if (!k.handles) continue
                    for (const s of ["out", "in"]) if (k[s]) poly(g, [k.pos, k[s]], false)
                }
            }
        }
        function poly(g, pts, closed) {
            if (pts.length < 2) return
            g.beginPath()
            g.moveTo(mp.cx(pts[0]), mp.cy(pts[0]))
            for (let i = 1; i < pts.length; i++) g.lineTo(mp.cx(pts[i]), mp.cy(pts[i]))
            if (closed) g.closePath()
            g.stroke()
        }
        Connections { target: mp; function onPathsChanged() { ink.requestPaint() }
                      function onFitChanged() { ink.requestPaint() } function onOxChanged() { ink.requestPaint() }
                      function onOyChanged() { ink.requestPaint() } }
    }

    // Key squares and handle ends: a small mark with a larger invisible target. The Repeaters keep their marks
    // (KeptRepeater), so a drag's changes update the marks in place and the pressed one keeps its drag.
    readonly property var squares: {
        const fit = mp.fit, hit = mp.hit      // read here, so the squares follow a zoom (a read inside a callback is not tracked)
        const all = []
        for (const row of mp.paths)
            if (!row.faint || mp.interactive)
                for (const k of row.keys) all.push({ id: row.id, t: k.t, side: "", p: k.pos, picked: k.picked, faint: row.faint })
        // Keys whose targets would touch (a cut's two keys one frame apart in one place; two layers' keys on one spot) stand as
        // one square: the picked one first, else the first; so no two squares are closer than a target.
        const out = []
        for (const sq of all.filter(q => q.picked).concat(all.filter(q => !q.picked)))
            if (!out.some(o => Math.max(Math.abs(o.p[0] - sq.p[0]), Math.abs(o.p[1] - sq.p[1])) * fit < hit)) out.push(sq)
        return out
    }
    readonly property var knobs: {       // a handle end whose target would touch a square's (or another end's) is left out until zoomed in
        const out = [], fit = mp.fit, hit = mp.hit
        const near = (a, b) => Math.max(Math.abs(a[0] - b[0]), Math.abs(a[1] - b[1])) * fit < hit
        for (const row of mp.paths)
            for (const k of row.keys)
                if (k.handles) for (const s of ["out", "in"])
                    if (k[s] && !mp.squares.some(q => near(q.p, k[s])) && !out.some(o => near(o.p, k[s])))
                        out.push({ id: row.id, t: k.t, side: s, p: k[s] })
        return out
    }
    KeptRepeater { needed: mp.squares.length; delegate: Mark { info: mp.squares[index] || ({}) } }   // kept: another layer's keys
    KeptRepeater { needed: mp.knobs.length; delegate: Mark { info: mp.knobs[index] || ({}) } }     // reuse the marks (a mark past them: no info, hidden)

    component Mark: Item {
        id: mark
        required property int index
        property var info: ({})
        readonly property bool knob: info.side !== ""
        visible: info.p !== undefined
        x: info.p ? mp.cx(info.p) - mp.hit / 2 : 0; y: info.p ? mp.cy(info.p) - mp.hit / 2 : 0
        width: mp.hit; height: mp.hit
        Rectangle {
            anchors.centerIn: parent
            width: mark.knob ? 10 : 8; height: width; radius: mark.knob ? width / 2 : 0      // a knob lying on the path still shows
            color: mark.knob || mark.info.picked ? Theme.accent : "white"
            border.width: mark.knob ? 2 : 1; border.color: mark.knob ? "white" : Theme.accent
            opacity: mark.info.faint ? 0.6 : 1
        }
        MouseArea {
            anchors.fill: parent
            enabled: mp.interactive && !spaceKey.held
            cursorShape: pressed ? Qt.ClosedHandCursor : Qt.PointingHandCursor
            preventStealing: true
            property bool going: false
            property real sx: 0
            property real sy: 0
            onPressed: (m) => {
                const q = mapToItem(mp, m.x, m.y); sx = q.x; sy = q.y
                const i = mark.info
                going = mark.knob ? backend.motionPath.beginHandle(i.id, i.t, i.side) : backend.motionPath.beginKey(i.id, i.t)
            }
            onPositionChanged: (m) => {
                if (!going) return
                const q = mapToItem(mp, m.x, m.y)
                backend.snap.keys(Mods.ctrl(m) || Mods.alt(m), false)             // Ctrl or Alt: place freely
                backend.motionPath.drag((q.x - sx) / mp.fit, (q.y - sy) / mp.fit, Mods.alt(m))
            }
            onReleased: { if (going) backend.endDrag(); going = false }
            onCanceled: { if (going) backend.endDrag(); going = false }
        }
    }
}
