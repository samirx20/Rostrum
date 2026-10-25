import QtQuick
import RostrumKit
import "KeyGroups.js" as KeyGroups

// A timeline row's time side (LayerRows.qml), under the ruler (x = ruler.x - 8). A layer row with a time (rowData.bar,
// start, end) draws its bar from start to end, with or without keys, its name written inside at the left (rowData.trim:
// 2D); the frame's bar (rowData.frame) is the whole scene and is never dragged. Without start and end (3D) the bar runs
// from the first key to the last. A selected layer's bar is drawn brighter with an accent outline, the row itself stays
// as it is (Sam, H49: no box across the whole row). Drag the bar to move the layer in time, drag an end to trim it:
// backend.beginBarDrag(id, "move" | "start" | "end") / barDragTo / endDrag (one gesture = one change; near a marker or
// the playhead it snaps; let go on a marker: tied). An end tied to a marker is a small flag at that time.
// Keys sit on it as diamonds (all the layer's keys; keys closer than a dot's width (16 px) share one, a second diamond behind it, until zoomed in: KeyGroups.js); a drawing's frames lie on it (FrameMarks). Setting, effect and
// mask rows show their keys only. Click a diamond: the key is selected (the inspector shows its ease); drag it: key.set
// t (it lands on a marker within 6 px). Between two keys of one setting a stretch can be clicked (StretchBand.qml). A click anywhere else on the row selects its layer, a drag there draws a box
// that picks every key it touches (on several rows). The ease shows in the settings panel when a stretch or key is
// clicked, not on the row. The ruler scrubs.
// Past the last key, Repeat and Back and forth show faint copies of the keys; a spring cut short by its next key, a
// faint tail to where it would have settled (screen2d/key_ghosts.py, from the evaluator's own functions).
Rectangle {
    id: track
    property var rowData
    property Item ruler
    readonly property bool isLayer: rowData.row === "layer"
    readonly property bool lit: rows && rows.lit !== undefined ? rows.lit[rowData.owner] !== undefined     // every selected layer's bar: the list's one
                                : rowData.owner === backend.selected || backend.multi.ids.indexOf(rowData.owner) >= 0  // lookup (2D LayerRows.qml), else read here
    function xOf(t) { return 8 + Math.round(ruler.xOf(t)) }
    function onBar(k) { return k.t >= (rowData.start || 0) - 1e-6 && k.t <= (rowData.end || 0) + 1e-6 }   // a key in the layer's time
    function tAt(item, x) { return ruler.tOf(item.mapToItem(track, x, 0).x - 8) }
    property var frozen: null           // while a key is held: the dots as they were at the press (hold / release)
    function dots(keys) { return frozen ? KeyGroups.regroup(keys, frozen) : KeyGroups.group(keys, xOf, 16) }   // keys whose click areas (a dot is 16 px wide, KeyDot.qml) would touch: one dot for the run
    function hold() { frozen = barDots.concat(loneDots).map(d => d.members) }
    function release() { frozen = null }
    readonly property bool fixed: rowData.frame === true       // the frame's bar: the whole scene, never slid or trimmed
    readonly property bool trims: rowData.trim === true && !fixed   // its ends can be dragged (2D layers; 3D's bar is only its keys)
    readonly property bool named: rowData.trim === true         // the layer's name is written in the bar
    readonly property bool hasCells: (rowData.frames || []).length > 0     // a drawing's cells are its bar: no second one over them
    readonly property bool hasBar: isLayer && rowData.bar === true && !hasCells && (trims || fixed || rowData.keys.some(k => onBar(k)))
    // The dots, as lists: a Repeater over a count keeps its delegates when the data changes (a Repeater over the list
    // itself rebuilds every dot at each change of the document, which dropped a key under the pointer mid-drag).
    readonly property var barDots: hasBar ? dots(rowData.keys.filter(k => onBar(k))) : []
    readonly property var loneDots: dots(hasBar ? rowData.keys.filter(k => !onBar(k)) : rowData.keys)
    radius: Theme.radiusCtl
    color: isLayer ? Theme.sunken : Qt.darker(Theme.panel, 1.15)

    property Component cells            // the app's own marks on the row, under the keys (2D: FrameMarks.qml)
    property Item rows                  // the rows it lies in (2D: LayerRows.qml): a box dragged here picks keys on every row it touches
    // Right-click anywhere on the row (its empty part, its bar, a stretch, a key): the one short menu (actions.SHORT_MENU)
    function openMenu(item, x, y) { const p = item.mapToItem(rows, x, y); rows.openMenu(rowData.owner, p.x, p.y) }
    MouseArea {   // the row's empty part, and the gap under it: a click selects its layer, a drag draws a box that picks keys
        anchors { fill: parent; bottomMargin: rows ? -rows.spacing : 0 }      // the gap between rows is the row above's, so a box can start there too
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        property point from
        property bool boxing: false
        onPressed: (m) => {
            boxing = false
            if (m.button === Qt.RightButton) { from = Qt.point(-1e6, -1e6); track.openMenu(this, m.x, m.y); return }
            from = Qt.point(m.x, m.y)
        }
        onPositionChanged: (m) => {
            if (from.x < -1e5) return                     // a right press: the menu, no box
            if (!boxing && Math.abs(m.x - from.x) + Math.abs(m.y - from.y) < 5) return
            if (!boxing) { boxing = true; track.rows.boxStart(mapToItem(track.rows.contentItem, from.x, from.y)) }
            track.rows.boxTo(mapToItem(track.rows.contentItem, m.x, m.y))
        }
        onReleased: (m) => {
            if (m.button === Qt.RightButton) return
            if (boxing) track.rows.boxEnd(m.modifiers & Qt.ControlModifier ? "ctrl" : m.modifiers & Qt.ShiftModifier ? "shift" : "")
            else { backend.keys.clear(); backend.select(track.rowData.owner) }   // a click on the row lets picked keys go
            boxing = false
        }
        onCanceled: { if (boxing) track.rows.boxEnd("cancel"); boxing = false }
    }
    Rectangle {  // the bar: start to end (3D: first key to last key), centred in the row
        id: bar
        objectName: "bar:" + track.rowData.id
        visible: track.hasBar
        opacity: track.rowData.hidden ? 0.35 : 1       // a hidden layer dims
        readonly property real pad: track.named || track.fixed ? 0 : 8   // 3D: half a dot (16, KeyDot.qml) so the end dots fit whole
        readonly property var span: track.hasBar ? [track.rowData.start || 0, track.rowData.end || 0] : [0, 0]
        x: track.xOf(span[0]) - pad
        width: Math.max(track.named ? 8 : 0, track.xOf(span[1]) + pad - x)
        height: track.named ? 18 : 12; y: Math.round((parent.height - height) / 2); radius: height / 2
        color: track.lit ? Qt.tint(Theme.line, Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.5))
                         : barArea.containsMouse && !track.fixed ? Theme.lineHover : Theme.line
        border.width: track.lit ? 1 : 0; border.color: Theme.accent
        Text {   // the layer's name, at the left, when there is room
            visible: track.named && width > 24
            x: 8; width: bar.width - 12; anchors.verticalCenter: parent.verticalCenter
            text: track.rowData.label; elide: Text.ElideRight; font.family: uiFont; font.pixelSize: Theme.label
            color: track.lit ? Theme.fg : Theme.fg2
        }
        MouseArea {
            id: barArea
            anchors.fill: parent; hoverEnabled: true; preventStealing: true
            acceptedButtons: Qt.LeftButton | Qt.RightButton
            cursorShape: track.fixed ? Qt.ArrowCursor : held ? Qt.ClosedHandCursor : Qt.OpenHandCursor
            property string held: ""
            onPressed: (m) => {          // a selected bar moves every selected bar (drags.py); else it is selected alone
                if (m.button === Qt.RightButton) { track.openMenu(barArea, m.x, m.y); return }
                if (!backend.multi.has(track.rowData.id)) backend.select(track.rowData.id)
                if (track.fixed) return
                held = backend.beginBarDrag(track.rowData.id, "move", track.tAt(barArea, m.x)) === false ? "" : "move"
            }
            onPositionChanged: (m) => {
                if (!held) return
                backend.barDragTo(track.tAt(barArea, m.x), (m.modifiers & Qt.ControlModifier) ? 0 : 6 / track.ruler.perSec)
            }
            onReleased: { if (held) backend.endDrag(); held = "" }
            onCanceled: { if (held) backend.endDrag(); held = "" }
        }
        Repeater {   // the stretches of the animations on the layer's first line, under its keys (SPEC §9.2)
            model: track.hasBar ? track.rowData.stretches || [] : []
            delegate: StretchBand { row: track; shift: bar.x; room: bar.width }
        }
        Repeater {   // the two ends: 16 px each, centred on the edge, drag = trim the layer (start / end); beside the keys (a key at the edge keeps its diamond, the handle moves just outside it)
            model: track.trims ? ["start", "end"] : []
            delegate: MouseArea {
                id: grab
                objectName: "barEnd:" + track.rowData.id + ":" + modelData
                required property string modelData
                property string held: ""
                // A key whose diamond (16 px) lies over the handle: the key keeps its place, and the handle moves to just outside
                // the diamond (16 px), where nothing else is; with no room there (a key at 0 s: the names column is beside it)
                // the end has no handle and the bar's middle drags the layer. `near`: the keys' distances from this edge, inward.
                readonly property bool atStart: modelData === "start"
                readonly property var near: bar.visible ? track.barDots.map(d => (track.xOf(d.t) - bar.x - (atStart ? 0 : bar.width)) * (atStart ? 1 : -1))
                                                                .filter(v => v > -16 && v < 16) : []
                readonly property real outside: near.length ? (atStart ? Math.min(...near) - 8 - 16 : bar.width - Math.min(...near) + 8) : 0
                readonly property bool room: !near.length || (atStart ? bar.x + outside >= 0 : bar.x + outside + 16 <= track.width)
                enabled: room; visible: room
                x: near.length ? outside : (atStart ? 0 : bar.width) - width / 2
                width: 16; height: bar.height
                hoverEnabled: true; preventStealing: true; cursorShape: Qt.SizeHorCursor
                acceptedButtons: Qt.LeftButton | Qt.RightButton
                onPressed: (m) => {
                    if (m.button === Qt.RightButton) { track.openMenu(grab, m.x, m.y); return }
                    if (!backend.multi.has(track.rowData.id)) backend.select(track.rowData.id)
                    held = backend.beginBarDrag(track.rowData.id, modelData, track.tAt(grab, m.x)) === false ? "" : modelData
                }
                onPositionChanged: (m) => {
                    if (held) backend.barDragTo(track.tAt(grab, m.x), (m.modifiers & Qt.ControlModifier) ? 0 : 6 / track.ruler.perSec)
                }
                onReleased: { if (held) backend.endDrag(); held = "" }
                onCanceled: { if (held) backend.endDrag(); held = "" }
            }
        }
        Repeater {   // a layer's keys lie in its bar: pressed on a key, the key moves; anywhere else, the bar
            model: track.barDots.length
            delegate: KeyDot { row: track; list: track.barDots; shift: bar.x; room: bar.width }
        }
    }
    Loader { anchors.fill: parent; sourceComponent: track.cells }   // the app's own marks on the row (2D: a drawing's cells, FrameMarks.qml)
    Repeater {   // a tied end: a small flag with the marker's name on hover
        model: [{ at: "start", name: track.rowData.startMarker || "" }, { at: "end", name: track.rowData.endMarker || "" }]
        delegate: Rectangle {
            required property var modelData
            visible: track.rowData.bar === true && modelData.name !== ""
            x: track.xOf(modelData.at === "start" ? track.rowData.start || 0 : track.rowData.end || 0) - (modelData.at === "start" ? 0 : width); y: 1
            width: 7; height: 7; radius: 1; color: Theme.warn
            HoverHandler { id: flagHover }
            HoverTip { hovered: flagHover.hovered; text: (modelData.at === "start" ? "Starts at marker " : "Ends at marker ") + modelData.name }
        }
    }
    Repeater {   // the frame's cuts (rowData.cuts): a short orange tick at each, as on the ruler above
        model: track.rowData.cuts || []
        delegate: Rectangle {
            required property var modelData
            x: track.xOf(modelData) - 1; y: 2; width: 2; height: track.height - 4; radius: 1; z: 3
            color: Theme.warn
        }
    }
    Repeater {   // a spring still moving at its next key: a faint tail to where it would have settled (key_ghosts.py)
        model: track.rowData.tails || []
        delegate: Rectangle {
            required property var modelData
            x: track.xOf(modelData.t0); width: Math.max(2, track.xOf(modelData.t1) - x)
            y: track.height / 2 - 1.5; height: 3; radius: 1.5; z: 1
            color: Theme.fg3; opacity: tailHover.hovered ? 0.7 : 0.35
            HoverHandler { id: tailHover }
            HoverTip { hovered: tailHover.hovered; text: "The spring is still moving here: at the key it jumps. Move the key this much later for it to settle." }
        }
    }
    Repeater {   // Repeat / Back and forth: faint copies of the keys after the last one, as playback plays them (key_ghosts.py)
        model: track.rowData.ghosts || []
        delegate: Rectangle {
            required property var modelData
            width: 7; height: 7; rotation: 45; z: 1
            x: track.xOf(modelData) - width / 2; y: (track.height - height) / 2
            color: "transparent"; border.width: 1; border.color: Theme.fg2; opacity: 0.45
        }
    }
    Repeater {   // a line's stretches (or a barless layer's), under its keys
        model: track.hasBar || track.hasCells ? [] : track.rowData.stretches || []
        delegate: StretchBand { row: track }
    }
    Repeater {   // the keys of a row with no bar (a setting, an effect, a mask)
        model: track.loneDots.length
        delegate: KeyDot { row: track; list: track.loneDots }
    }
}
