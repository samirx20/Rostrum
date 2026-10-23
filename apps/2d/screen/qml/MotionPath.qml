import QtQuick
import RostrumKit
import "Mods.js" as Mods

// The motion path over the canvas (screen2d/motion_path.py does the work): where the selected layer travels, a dot per
// frame (close dots: slow, far apart: fast), a square per key (filled when picked) and the picked or bent keys' handles;
// for the camera, its frame now and a faint one at each key. Drag a square: the key moves, snapping as a layer does (Ctrl or Alt: free); drag a handle end: the path
// bends, the opposite handle mirrored (Alt: not). One drag = one change. Hidden while playing. Positions come in
// composition px as the canvas shows them; fit / ox / oy are the Stage's one mapping (canvas px = o + comp px × fit).
Item {
    id: mp
    property real fit: 1
    property real ox: 0
    property real oy: 0
    property bool interactive: true
    property real compW: 0                      // the picture's size in composition px: the camera's frames are cut at its edge
    property real compH: 0
    readonly property var paths: backend.motionPath.paths
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
                const alpha = row.faint ? 0.35 : 0.7
                const ac = Qt.rgba(a.r, a.g, a.b, alpha)
                g.lineWidth = 1
                g.strokeStyle = Qt.rgba(a.r, a.g, a.b, row.faint ? 0.25 : 0.5)
                g.save()                                                       // frames stay inside the picture, never run into the margin
                if (mp.compW > 0) { g.beginPath(); g.rect(mp.ox, mp.oy, mp.compW * mp.fit, mp.compH * mp.fit); g.clip() }
                for (const f of row.frames) poly(g, f, true)                   // the camera at each key
                g.strokeStyle = ac
                if (row.now.length) poly(g, row.now, true)                     // the camera's frame now
                g.restore()
                g.strokeStyle = ac
                poly(g, row.points, false)
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
                      function onOyChanged() { ink.requestPaint() }
                      function onCompWChanged() { ink.requestPaint() } function onCompHChanged() { ink.requestPaint() } }
    }

    // Key squares and handle ends: a small mark with a larger invisible target. The Repeaters count marks (an int
    // model), so a drag's changes update the marks in place and the pressed one keeps its drag.
    readonly property var squares: {
        const out = []
        for (const row of mp.paths)
            if (!row.faint || mp.interactive)
                for (const k of row.keys) out.push({ id: row.id, t: k.t, side: "", p: k.pos, picked: k.picked, faint: row.faint })
        return out
    }
    readonly property var knobs: {
        const out = []
        for (const row of mp.paths)
            for (const k of row.keys)
                if (k.handles) for (const s of ["out", "in"]) if (k[s]) out.push({ id: row.id, t: k.t, side: s, p: k[s] })
        return out
    }
    Repeater { model: mp.squares.length; delegate: Mark { info: mp.squares[index] || ({}) } }
    Repeater { model: mp.knobs.length; delegate: Mark { info: mp.knobs[index] || ({}) } }

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
