import QtQuick
import RostrumKit

// The piano roll's drawing (clicks on the notes are PianoRoll's): rows (one per key, darker for black keys, or one per
// drum), at the left a real keyboard (white and black keys, a C label on every octave; press a key to hear it, drag
// across to play each one: backend.playKey) or the drum names, the beat grid, and the track's notes, hits or clips
// (RollNotes.qml, painted).
// rowAt(y) is the one mapping from height to a key (MIDI number), a drum row, or 0 for clips. Key rows have one
// height, keyRow, whatever the track, its notes or an undo (rows that re-fitted on every open and undo, 12 / 13.3 / 16 px,
// put clicks on the wrong keys: critic r11); the key range is always taller than the view (timeline.roll).
Item {
    id: g
    property var roll
    property var blocks: []     // the roll's notes / hits / clips (sent apart from its layout)
    property var ruler
    property int keysWidth: 52
    property real viewHeight: 400
    signal drumMenuAt(string drum, real x, real y)     // right-click on a drum's name (PianoRoll opens its menu)
    property real scrollY: 0               // how far the view is scrolled: a row name shows only while its row is whole
    readonly property bool notes: roll.kind === "notes"
    readonly property var shownKeys: roll.rows || null       // Only the key's rows: the keys shown, top first (null = every key from hi to lo)
    readonly property var rowIdx: { if (!shownKeys) return null; var m = {}; for (var i = 0; i < shownKeys.length; i++) m[shownKeys[i]] = i; return m }
    readonly property int count: notes ? (shownKeys ? shownKeys.length : roll.hi - roll.lo + 1) : roll.kind === "drums" ? Math.max(1, roll.drums.length) : 1
    readonly property real keyRow: 12
    readonly property real rowH: notes ? Math.max(viewHeight / count, keyRow)
                               : roll.kind === "drums" ? Math.min(56, viewHeight / count) : viewHeight
    // A drum hit's diamond, centred on its time on its row: half its width (and height) in px. The one place: RollNotes
    // draws it this size, RollInput catches a click anywhere on it (backend.rollAt, a hit is caught either side of its time).
    readonly property real hitHalf: Math.min(12, rowH * 0.5) * 0.7071
    // a drum's stored name ("openHat", "kick") in words for the row: "Open hat", "Kick"
    function drumName(d) {
        if (!d) return ""
        var s = String(d).replace(/_/g, " ").replace(/([a-z])([A-Z0-9])/g, "$1 $2").toLowerCase()
        return s.charAt(0).toUpperCase() + s.slice(1)
    }
    // The one mapping between a key and its row: every painted key, lit key, name, note and click goes through these two.
    function keyAtRow(i) { return shownKeys ? shownKeys[Math.max(0, Math.min(shownKeys.length - 1, i))] : roll.hi - i }
    function rowOf(key) { if (!rowIdx) return roll.hi - key; var i = rowIdx[key]; return i === undefined ? -2 : i }
    function shows(key) { return rowIdx ? rowIdx[key] !== undefined : key <= roll.hi && key >= roll.lo }
    function rowAt(y) { var i = Math.floor(y / rowH); return notes ? keyAtRow(i) : roll.kind === "drums" ? i : 0 }
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

    // The rows and the keyboard, painted on one surface: an item per key (a dozen each) made ~600 items again each
    // time the roll's key range changed (another track, a note past the top key: ~30 ms). Only what moves or names a
    // key stays an item: the lit key, the C names, the drums' names.
    Canvas {
        id: rows
        visible: g.roll.kind !== "audio"
        width: Math.max(g.width, Screen.width); height: g.height     // as wide as the screen: a resize keeps the picture
        readonly property var look: [g.roll, g.rowH, g.count, g.keyed, g.rowInKey, g.keyRoot, g.keysWidth, Theme.app]
        onLookChanged: requestPaint()
        onHeightChanged: requestPaint()
        // a song opened with the Editor showing paints before the window has its width (0 wide): paint again when it
        // comes, or the roll shows no keys and no row stripes until the first scroll (production round, piano piece)
        onWidthChanged: requestPaint()
        onAvailableChanged: if (available) requestPaint()
        onPaint: {
            var ctx = getContext("2d"); ctx.reset()
            var h = g.rowH, kw = g.keysWidth, n = g.count, W = width
            for (var i = 0; i < n; i++) {
                var y = i * h, key = g.keyAtRow(i)
                if (!g.notes) {
                    ctx.fillStyle = Theme.border; ctx.fillRect(kw, y + h - 1, W - kw, 1)
                    ctx.fillStyle = Theme.panel; ctx.fillRect(0, y, kw - 6, h - 1)
                    continue
                }
                var blk = g.black(key)
                if (blk) { ctx.fillStyle = Theme.app; ctx.fillRect(kw, y, W - kw, h) }
                if (g.keyed) {            // in the key: lighter; out: darker (a clear step between the two)
                    var inKey = g.rowInKey[i]
                    ctx.globalAlpha = inKey ? 1 : 0.75; ctx.fillStyle = inKey ? Theme.raised : "black"
                    ctx.fillRect(kw, y, W - kw, h); ctx.globalAlpha = 1
                }
                if (key % 12 === 0) { ctx.fillStyle = Theme.border; ctx.fillRect(kw, y + h - 1, W - kw, 1) }
                else if (g.shownKeys) { ctx.globalAlpha = 0.45; ctx.fillStyle = Theme.border; ctx.fillRect(kw, y + h - 1, W - kw, 1); ctx.globalAlpha = 1 }
                paintKey(ctx, key, y, h, kw - 2, "#d6d6d6", "#161616")
            }
        }
        function paintKey(ctx, key, y, h, w, white, black) {      // a white key, or a black one over the white behind it
            ctx.fillStyle = g.black(key) ? "#d6d6d6" : white; ctx.fillRect(0, y, w, h)
            ctx.fillStyle = "#8a8a8a"
            if (g.shownKeys) {            // Only the key's rows: each row its own key, a line under every one
                ctx.fillRect(0, y + h - 1, w, 1)
                if (g.black(key)) { ctx.fillStyle = black; ctx.beginPath(); ctx.roundedRect(0, y, Math.round(w * 0.6), h - 1, 2, 2); ctx.fill() }
            } else if (key % 12 === 0 || key % 12 === 5) ctx.fillRect(0, y + h - 1, w, 1)   // B | C and E | F touch
            if (!g.shownKeys && g.black(key)) {
                ctx.fillRect(0, y + Math.floor(h / 2), w, 1)                       // the line between its two white keys
                ctx.fillStyle = black; ctx.beginPath(); ctx.roundedRect(0, y, Math.round(w * 0.6), h, 2, 2); ctx.fill()
            }
            if (g.keyRoot === key % 12) { ctx.fillStyle = Theme.accent; ctx.fillRect(w - 3, y, 3, h) }   // the key's root
        }
    }
    Repeater {   // the lit key (under the pointer or pressed), over the painted one, with its name
        model: g.notes && g.litKey >= 0 && g.shows(g.litKey) ? 1 : 0
        Item {
            readonly property int key: g.litKey
            readonly property bool down: g.downKey === key
            y: g.rowOf(key) * g.rowH; width: g.keysWidth - 2; height: g.rowH
            Rectangle { anchors.fill: parent; color: g.black(parent.key) ? "#d6d6d6" : parent.down ? Theme.accent : "#f2f2f2" }
            Rectangle { visible: [0, 5].indexOf(parent.key % 12) >= 0; width: parent.width; height: 1; y: parent.height - 1; color: "#8a8a8a" }
            Rectangle { visible: g.black(parent.key); width: parent.width; height: 1; y: Math.floor(parent.height / 2); color: "#8a8a8a" }
            Rectangle { visible: g.black(parent.key); width: Math.round(parent.width * 0.6); height: parent.height; radius: 2
                        color: parent.down ? Theme.accent : "#3a3a3a" }
            Rectangle { visible: g.keyRoot === parent.key % 12; x: parent.width - 3; width: 3; height: parent.height; color: Theme.accent }
            KeyName { key: parent.key; row: g.rowOf(parent.key) }
        }
    }
    Repeater {   // C on every octave (C4 = middle C)
        model: g.notes ? Math.floor(g.roll.hi / 12) - Math.ceil(g.roll.lo / 12) + 1 : 0
        KeyName { required property int index; key: 12 * (Math.ceil(g.roll.lo / 12) + index); row: g.rowOf(key)
                  y: row * g.rowH; visible: g.litKey !== key && g.shows(key) }
    }
    component KeyName: Item {     // a key's name on the keyboard: "C4", or the key under the pointer's name in the song's key
        property int key
        property int row                                 // its row from the top
        readonly property real rowY: row * g.rowH
        readonly property bool whole: rowY >= g.scrollY - 1 && rowY + g.rowH <= g.scrollY + g.viewHeight + 1   // a row cut by the edge: no name
        width: g.keysWidth - 2; height: g.rowH
        Text {
            visible: g.rowH >= 7 && parent.whole
            anchors { right: parent.right; rightMargin: 4; verticalCenter: parent.verticalCenter }
            text: parent.key % 12 === 0 ? "C" + (Math.floor(parent.key / 12) - 1) : (g.rowNames[parent.row] || "")
            color: g.black(parent.key) ? "#e6e6e6" : "#3c3c3c"
            font.family: uiFont; font.pixelSize: Math.min(Theme.label - 1, Math.max(9, g.rowH)); font.features: { "tnum": 1 }
            font.weight: parent.key % 12 === 0 ? Font.DemiBold : Font.Normal
        }
    }
    Repeater {   // a drum's name
        model: g.roll.kind === "drums" ? g.count : 0
        Item {
            id: nameCell
            required property int index
            readonly property string drum: g.roll.drums[index]
            y: index * g.rowH
            visible: y >= g.scrollY - 1 && y + height <= g.scrollY + g.viewHeight + 1
            x: 0; width: g.keysWidth - 6; height: g.rowH
            Text {
                x: Theme.gap; width: parent.width - Theme.gap; height: parent.height     // fits its row: a short row shrinks the name
                verticalAlignment: Text.AlignVCenter; fontSizeMode: Text.Fit; minimumPixelSize: 7
                elide: Text.ElideRight
                text: g.drumName(nameCell.drum); color: nameHover.containsMouse ? Theme.fg : Theme.fg3
                font.family: uiFont; font.pixelSize: Theme.label
            }
            Item { objectName: "action:fill_row"; anchors.fill: parent; visible: backend.fillDrum === nameCell.drum }   // Fill row… opens under its name
            MouseArea {   // click: hear the drum and select its hits; right-click: its menu (Fill ▸, Clear …)
                id: nameHover
                objectName: "drumRow_" + nameCell.drum
                anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                acceptedButtons: Qt.LeftButton | Qt.RightButton
                onClicked: (m) => { if (m.button === Qt.RightButton) g.drumMenuAt(nameCell.drum, m.x + parent.x, m.y + parent.y); else backend.drumRowClicked(nameCell.drum) }
            }
        }
    }
    property int hoverKey: -1
    property int downKey: -1
    readonly property int litKey: downKey >= 0 ? downKey : hoverKey
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

    RollNotes { grid: g; x: g.keysWidth; width: g.width - x; height: g.height }   // the notes, hits and clips (painted)
}
