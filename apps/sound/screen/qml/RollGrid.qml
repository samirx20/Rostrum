import QtQuick
import RostrumKit

// The piano roll's drawing (clicks on the notes are PianoRoll's): rows (one per key, darker for black keys, or one per
// drum), at the left a real keyboard (white and black keys, a C label on every octave; press a key to hear it, drag
// across to play each one: backend.playKey) or the drum names, the beat grid, and the track's notes, hits or clips.
// rowAt(y) is the one mapping from height to a key (MIDI number), a drum row, or 0 for clips. frame(n): rows high
// enough that n keys (the track's notes) fit the view, at least 7 px (PianoRoll calls it when it opens on a track).
Item {
    id: g
    property var roll
    property var ruler
    property int keysWidth: 52
    property real viewHeight: 400
    property real scrollY: 0               // how far the view is scrolled: a row name shows only while its row is whole
    readonly property bool notes: roll.kind === "notes"
    readonly property int count: notes ? roll.hi - roll.lo + 1 : roll.kind === "drums" ? Math.max(1, roll.drums.length) : 1
    property int fitRows: 0
    function frame(n) { fitRows = n }
    readonly property real rowH: notes ? Math.max(viewHeight / count, fitRows > 0 ? Math.max(7, Math.min(16, viewHeight / (fitRows + 2))) : 12)
                               : roll.kind === "drums" ? Math.min(56, viewHeight / count) : viewHeight
    // a drum's stored name ("openHat", "kick") in words for the row: "Open hat", "Kick"
    function drumName(d) {
        if (!d) return ""
        var s = String(d).replace(/_/g, " ").replace(/([a-z])([A-Z0-9])/g, "$1 $2").toLowerCase()
        return s.charAt(0).toUpperCase() + s.slice(1)
    }
    function rowAt(y) { var i = Math.floor(y / rowH); return notes ? roll.hi - i : roll.kind === "drums" ? i : 0 }
    // The row names follow the key in force at the view's left edge: scrolling past a key change renames the keys.
    readonly property var rowKey: {
        var list = roll.rowNames, at = ruler.start + 1e-6, hit = list.length ? list[0] : ({ names: [], inKey: [] })
        for (var i = 0; i < list.length; i++) if (list[i].t <= at) hit = list[i]
        return hit
    }
    readonly property bool keyed: rowKey.inKey.indexOf(false) >= 0     // a key is in force (with none, every row is equal)
    readonly property var rowNames: rowKey.names
    readonly property int keyRoot: rowKey.root !== undefined ? rowKey.root : -1     // the key's root note (0 … 11), -1 with no key
    readonly property var rowInKey: rowKey.inKey       // false: outside the song's key there, the row is shaded darker
    function black(k) { return [1, 3, 6, 8, 10].indexOf(k % 12) >= 0 }
    height: count * rowH

    Repeater {   // rows and their names
        model: g.roll.kind === "audio" ? 0 : g.count
        delegate: Item {
            required property int index
            readonly property int key: g.roll.hi - index
            y: index * g.rowH; width: g.width; height: g.rowH
            Rectangle { x: g.keysWidth; width: parent.width - x; height: parent.height
                        color: g.notes && g.black(parent.key) ? Theme.app : "transparent" }
            Rectangle { x: g.keysWidth; width: parent.width - x; height: parent.height     // in the key: lighter; out: darker
                        visible: g.notes && g.keyed; color: g.rowInKey[parent.index] ? Theme.raised : "black"
                        opacity: g.rowInKey[parent.index] ? 1 : 0.75 }   // a clear step between the two
            Rectangle { x: g.keysWidth; width: parent.width - x; height: 1; y: parent.height - 1
                        visible: g.notes ? parent.key % 12 === 0 : true; color: Theme.border }
            Item {   // the keyboard: a white key, or a black one over the white behind it
                visible: g.notes; width: g.keysWidth - 2; height: parent.height
                readonly property bool down: g.downKey === parent.key
                readonly property bool lit: down || g.hoverKey === parent.key
                Rectangle { anchors.fill: parent; color: !g.black(parent.parent.key) && parent.down ? Theme.accent
                                                        : !g.black(parent.parent.key) && parent.lit ? "#f2f2f2" : "#d6d6d6" }
                Rectangle {   // the line between two white keys that touch: B | C and E | F
                    visible: [0, 5].indexOf(parent.parent.key % 12) >= 0
                    width: parent.width; height: 1; y: parent.height - 1; color: "#8a8a8a" }
                Rectangle {   // behind a black key, the line between its two white keys
                    visible: g.black(parent.parent.key)
                    width: parent.width; height: 1; y: Math.floor(parent.height / 2); color: "#8a8a8a" }
                Rectangle {   // a black key: shorter, over the line between its two white keys
                    visible: g.black(parent.parent.key)
                    width: Math.round(parent.width * 0.6); height: parent.height; radius: 2
                    color: parent.down ? Theme.accent : parent.lit ? "#3a3a3a" : "#161616" }
                Text {   // C on every octave (C4 = middle C); the key under the pointer says its name
                    readonly property int k: parent.parent.key
                    z: 1
                    visible: (k % 12 === 0 || parent.lit) && g.rowH >= 7
                             && parent.parent.y >= g.scrollY - 1 && parent.parent.y + parent.parent.height <= g.scrollY + g.viewHeight + 1
                    anchors { right: parent.right; rightMargin: 4; verticalCenter: parent.verticalCenter }
                    text: k % 12 === 0 ? "C" + (Math.floor(k / 12) - 1) : g.rowNames[parent.parent.index]
                    color: g.black(k) ? "#e6e6e6" : "#3c3c3c"
                    font.family: uiFont; font.pixelSize: Math.min(Theme.label - 1, Math.max(9, g.rowH)); font.features: { "tnum": 1 }
                    font.weight: k % 12 === 0 ? Font.DemiBold : Font.Normal
                }
                Rectangle {   // the key's root (the song's key there): an accent tick at the keys' inner edge
                    visible: g.keyRoot === parent.parent.key % 12
                    x: parent.width - 3; width: 3; height: parent.height; color: Theme.accent }
            }
            Rectangle { visible: !g.notes; width: g.keysWidth - 6; height: parent.height - 1; color: Theme.panel }
            Text {   // a drum's name
                visible: !g.notes && parent.y >= g.scrollY - 1 && parent.y + parent.height <= g.scrollY + g.viewHeight + 1
                x: Theme.gap; width: g.keysWidth - Theme.gap - 6; height: parent.height     // fits its row: a short row
                verticalAlignment: Text.AlignVCenter; fontSizeMode: Text.Fit; minimumPixelSize: 7  // shrinks the name
                elide: Text.ElideRight
                text: g.drumName(g.roll.drums[parent.index]); color: Theme.fg3
                font.family: uiFont; font.pixelSize: Theme.label
            }
        }
    }
    property int hoverKey: -1
    property int downKey: -1
    MouseArea {   // the keyboard plays: press a key, or drag across the keys
        visible: g.notes; width: g.keysWidth - 2; height: g.height
        hoverEnabled: true; preventStealing: true; cursorShape: Qt.PointingHandCursor
        onPositionChanged: (m) => {
            g.hoverKey = g.rowAt(m.y)
            if (pressed && g.hoverKey !== g.downKey) { g.downKey = g.hoverKey; backend.playKey(g.downKey) }
        }
        onExited: g.hoverKey = -1
        onPressed: (m) => { g.downKey = g.rowAt(m.y); backend.playKey(g.downKey) }
        onReleased: g.downKey = -1
        onCanceled: g.downKey = -1
    }
    BeatGrid { x: g.keysWidth; width: g.width - x; height: g.height; ruler: g.ruler; opacity: 0.8 }

    readonly property var picked: backend.picked        // one read per change
    Item {   // the plot: zoomed in, what is out of view is cut at the keys' edge
        x: g.keysWidth; width: g.width - x; height: g.height; clip: true
        // One painted surface for the notes, hits and clips, not four items per note: only what is on screen is
        // painted, again when the roll, the zoom, the scroll, the selection or the size changes.
        Canvas {
            id: c
            anchors.fill: parent
            onWidthChanged: requestPaint()
            onHeightChanged: requestPaint()
            Connections {
                target: g
                function onRollChanged() { c.requestPaint() }
                function onPickedChanged() { c.requestPaint() }
                function onRowHChanged() { c.requestPaint() }
            }
            Connections {
                target: g.ruler
                function onStartChanged() { c.requestPaint() }
                function onPerSecChanged() { c.requestPaint() }
            }
            function fillOf(on) { return on ? Qt.lighter(g.roll.hue, 1.25) : g.roll.hue }      // selected: a lighter fill, the accent outline
            function round(ctx, x, y, w, h, r) { ctx.beginPath(); ctx.roundedRect(x, y, w, h, r, r) }
            function paintNote(ctx, b, on, x) {
                var w = Math.max(4, g.ruler.wOf(b.dur) - 1), h = g.rowH - 2
                ctx.font = "600 " + (Theme.label - 1) + "px '" + uiFont + "'"; ctx.textBaseline = "middle"
                for (var i = 0; i < b.keys.length; i++) {
                    var y = (g.roll.hi - b.keys[i]) * g.rowH + 1
                    ctx.fillStyle = fillOf(on); round(ctx, x, y, w, h, 3); ctx.fill()
                    if (on) { ctx.strokeStyle = Theme.accent; ctx.lineWidth = 2; round(ctx, x + 1, y + 1, w - 2, h - 2, 2); ctx.stroke() }
                    if (b.out && b.out[i] && w >= 10) {      // outside the key playing there: a small dot at the end
                        ctx.fillStyle = Theme.app; ctx.beginPath(); ctx.arc(x + w - 5, y + h / 2, 2.5, 0, 2 * Math.PI); ctx.fill()
                    }
                    if (g.rowH >= 14 && b.names[i] && w >= ctx.measureText(b.names[i]).width + (b.out && b.out[i] ? 14 : 5)) {      // whenever the name fits the bar
                        ctx.fillStyle = Theme.app; ctx.fillText(b.names[i], x + 3, y + h / 2)
                    }
                }
            }
            function paintHit(ctx, b, on, x) {                  // a diamond on its drum's row
                var cy = g.roll.drums.indexOf(b.drum) * g.rowH + g.rowH / 2
                var d = Math.min(12, g.rowH * 0.5) * 0.7071
                ctx.globalAlpha = on ? 1 : 0.5 + 0.5 * (b.vel || 0)
                ctx.fillStyle = fillOf(on)
                ctx.beginPath(); ctx.moveTo(x, cy - d); ctx.lineTo(x + d, cy); ctx.lineTo(x, cy + d); ctx.lineTo(x - d, cy); ctx.closePath(); ctx.fill()
                if (on) { ctx.strokeStyle = Theme.accent; ctx.lineWidth = 2; ctx.stroke() }
                ctx.globalAlpha = 1
            }
            function paintClip(ctx, b, on, x) {
                var y = g.height * 0.2, h = g.height * 0.6, w = Math.max(4, g.ruler.wOf(b.dur))
                ctx.strokeStyle = on ? Theme.accent : g.roll.hue; ctx.lineWidth = 1
                round(ctx, x + 0.5, y + 0.5, w - 1, h - 1, 4); ctx.stroke()
                var peaks = b.peaks || [], n = peaks.length
                if (n > 0) {
                    var ix = x + 4, iw = w - 8, top = y + 24, ih = h - 28, pw = iw / n
                    ctx.globalAlpha = 0.85; ctx.fillStyle = on ? Theme.accent : g.roll.hue
                    for (var i = 0; i < n; i++) {
                        var ph = Math.max(1, ih * peaks[i])
                        ctx.fillRect(ix + i * pw, top + (ih - ph) / 2, Math.max(1, pw - 2), ph)
                    }
                    ctx.globalAlpha = 1
                }
                ctx.save(); ctx.beginPath(); ctx.rect(x + 8, y, Math.max(0, w - 16 - (b.canBack || b.canNext ? 38 : 0)), h); ctx.clip()      // the label stays inside its block, clear of the take arrows
                ctx.fillStyle = Theme.fg2; ctx.font = Theme.label + "px '" + uiFont + "'"; ctx.textBaseline = "top"
                var room = Math.max(0, w - 16 - (b.canBack || b.canNext ? 38 : 0)), text = b.label || ""
                if (ctx.measureText(text).width > room) {      // a whole letter, then an ellipsis
                    while (text.length > 1 && ctx.measureText(text + "…").width > room) text = text.slice(0, -1)
                    text += "…"
                }
                ctx.fillText(text, x + 8, y + 6)
                ctx.restore()
            }
            onPaint: {
                var ctx = getContext("2d"); ctx.reset()
                var blocks = g.roll.blocks || [], picked = g.picked
                for (var pass = 0; pass < 2; pass++) {          // what is selected is drawn last, on top
                    for (var i = 0; i < blocks.length; i++) {
                        var b = blocks[i], on = !!picked[b.id]
                        if (on !== (pass === 1)) continue
                        var x = Math.round(g.ruler.xOf(b.t))
                        if (x > width + 12 || x + g.ruler.wOf(b.dur) < -12) continue        // off screen
                        if (b.type === "note") paintNote(ctx, b, on, x)
                        else if (b.type === "hit") paintHit(ctx, b, on, x)
                        else if (b.type === "clip" || b.type === "line" || b.type === "sound") paintClip(ctx, b, on, x)
                    }
                }
            }
        }
    }
}
