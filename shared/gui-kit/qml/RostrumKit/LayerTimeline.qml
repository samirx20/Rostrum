import QtQuick
import RostrumKit

// The key timeline, bottom, full width, always there; it is also the layers list (apps/2d/DESIGN.md › The layer rows;
// TIMELINE.md › The key timeline: what `backend` offers it). One header row: play and the time over the names, the
// ruler over the rows (it scrubs; the project's marker flags sit on it), Keys | Curves and the height switch at its
// right end. Under it one row per item, plugged in by the app (`rows`: a Flickable of rows, each a name and a
// LayerTrack.qml); Curves (`curves`) shows the selected item's value curves in the same place; `overlay` draws over
// the rows (2D: beat lines). The thin strip above the top edge drags to make the timeline taller.
// Compact (DESIGN.md › two heights): only the selected layer's row; its name opens a list of every layer, so another
// is one click away. The button at the ruler row's right end switches; the app remembers it per tool.
Rectangle {
    id: tl
    property int labelWidth: 240
    Item { property bool menuAvoid: true; x: 0; y: 0; width: tl.labelWidth; height: tl.height }   // menus and flyouts keep off the names (MenuPlace.js)
    signal resized(real height)                 // the top edge dragged to this height (Main.qml clamps it)
    property bool compact: false
    property bool canCompact: true              // false beside a tall frame (one height there): the switch is absent
    property bool canResize: true               // false where the app sets the height itself (3D's pages): no grab edge
    property bool canCurves: true               // false where the app has no curve view yet (3D): Keys | Curves is absent
    property string emptyText: ""               // an app with no rows yet words its items here (3D); 2D never has none: the Frame row is always there
    readonly property bool curvesOn: canCurves && backend.curves.on   // the app's one fact: chosen and something to see
    readonly property bool canPickRows: compact || backend.rowFacts.layerIds.includes(backend.selected)   // the height button: a layer is picked (or it is how back out of the one-row view)
    signal compactAsked(bool on)
    property Flickable rows                     // the app's rows (2D: LayerRows.qml), laid in place under the ruler
    property Item curves                        // the app's curve view, in the same place while Curves is on
    property Item overlay                       // drawn over the rows, under the markers and the playhead (2D: BeatLines.qml)
    property real compactExtra: 0               // rows that stay in compact too (2D: the Sound row)
    property bool frameTicks: false             // one tick per frame on the ruler (2D: a drawing selected)
    readonly property alias ruler: ruler
    readonly property real compactHeight: rowsTop + Theme.rowDense + 2 * Theme.gap + compactExtra
    readonly property real wantedHeight: rowsTop + (rows ? rows.contentHeight : 0) + 2 * Theme.gap   // header, ruler and every row: the app's default height, up to its cap
    function openMenu(id, px, py) { rows.openMenu(id, px, py) }
    function plug(item, into, z) { if (item) { item.parent = into; item.z = z; item.anchors.fill = into } }
    onRowsChanged: plug(rows, rowsBox, -1)          // under the fade and scroll bar that share its box
    onCurvesChanged: plug(curves, curvesBox, 0)
    onOverlayChanged: plug(overlay, overlayBox, 0)
    color: Theme.panel; radius: Theme.radiusPanel

    MouseArea {  // the top edge: in the gap above the timeline, so it never takes a click meant for the canvas
        id: edge
        visible: tl.canResize
        anchors { left: parent.left; right: parent.right; verticalCenter: parent.top }
        height: 2 * Theme.gap          // 16 px: easy to grab; half in the gap above, half on the timeline's own edge
        hoverEnabled: true; preventStealing: true
        cursorShape: Qt.SizeVerCursor
        property real y0: 0
        property real h0: 0
        onPressed: (m) => { y0 = mapToGlobal(m.x, m.y).y; h0 = tl.height }
        onPositionChanged: (m) => { if (pressed) tl.resized(h0 - (mapToGlobal(m.x, m.y).y - y0)) }
        Rectangle { anchors.centerIn: parent; width: 48; height: 3; radius: 1.5
                    color: edge.pressed ? Theme.accent : Theme.fg4; visible: edge.containsMouse || edge.pressed }
    }

    // The header row (SPEC §9.5): over the layer names, play, the time, Add marker (in a project folder) and Keys | Curves;
    // over the rows, the ruler, with the height switch at its right end. One row instead of two: the height is the rows'.
    readonly property real headY: Theme.gap                                   // room for the edge's grab above it
    readonly property real headH: Math.max(30, ruler.height)
    Row {
        id: playCell
        x: Theme.gap; y: tl.headY; height: tl.headH; spacing: Theme.gap
        z: readout.typing ? 1 : 0          // a long time being typed draws over Keys | Curves
        PlayButton { objectName: "timelinePlay"; anchors.verticalCenter: parent.verticalCenter; implicitHeight: 24; implicitWidth: 24
                     playing: backend.playing; onClicked: backend.togglePlay() }
        TimeReadout { id: readout; anchors.verticalCenter: parent.verticalCenter }
        AddMarker { anchors.verticalCenter: parent.verticalCenter }
    }
    Segmented {   // Keys: the rows' diamonds; Curves: the value curves inside this same area
        id: keysCurves
        objectName: "keysCurves"
        visible: tl.canCurves && backend.curves.offered    // curves to see (the app's `curves.offered`), else absent
        anchors { right: ruler.left; rightMargin: Theme.pad + 8; verticalCenter: ruler.verticalCenter }   // the names column's right edge
        implicitHeight: 26
        options: [{ value: "keys", label: "Keys" }, { value: "curves", label: "Curves" }]
        current: tl.curvesOn ? "curves" : "keys"
        onPicked: (v) => backend.curves.setOn(v === "curves")
    }
    TimeRuler {
        id: ruler
        x: tl.labelWidth + Theme.gap + 8; y: tl.headY   // 8: room for a key at 0
        width: (tl.canCompact ? parent.width - Theme.gap - compactSwitch.room - Theme.grid : parent.width - Theme.pad) - 8 - x; height: backend.markers.length > 0 ? 34 : 30   // 34: a row for marker flags
        duration: backend.frameInfo.duration; fps: backend.frameInfo.fps; time: backend.time; frameTicks: tl.frameTicks
        cuts: backend.rowFacts.cuts   // the frame's cuts (the Frame row is first; 3D has none)
    }
    Button {  // every row, or only the selected layer's: offered with a layer picked (or to get back from one row)
        id: compactSwitch
        objectName: "timelineHeight"
        visible: tl.canCompact && tl.canPickRows
        anchors { right: parent.right; rightMargin: Theme.gap; verticalCenter: ruler.verticalCenter }
        implicitHeight: 26; kind: "ghost"
        text: tl.compact ? "Show all layers" : "Only this layer"
        // its room is kept whether it shows or not (and whichever words it has), so the ruler never changes scale when a layer is picked
        readonly property real room: Math.max(wordsA.implicitWidth, wordsB.implicitWidth)
        width: room
        onClicked: tl.compactAsked(!tl.compact)
        Button { id: wordsA; visible: false; implicitHeight: 26; kind: "ghost"; text: "Only this layer" }
        Button { id: wordsB; visible: false; implicitHeight: 26; kind: "ghost"; text: "Show all layers" }
    }
    readonly property real rowsTop: ruler.y + ruler.height + Theme.grid
    Item {   // where `curves` lies
        id: curvesBox
        visible: tl.curvesOn
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom; top: parent.top
                  topMargin: tl.rowsTop; rightMargin: Theme.gap; bottomMargin: Theme.gap }   // x as the ruler's
    }
    Item {   // where `rows` lies, with its fade and scroll bar
        id: rowsBox
        visible: !tl.curvesOn
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom; top: parent.top
                  topMargin: tl.rowsTop; rightMargin: Theme.gap; bottomMargin: Theme.gap }   // x as the ruler's
        EdgeFade { flick: tl.rows; anchors.fill: parent; color: Theme.panel }   // a half-shown row fades, never a sliver
        VScrollBar { flick: tl.rows; visible: !!tl.rows && needed }
    }
    MouseArea {  // compact: the one row's name is a list of every layer
        visible: tl.compact && !tl.curvesOn && backend.rowFacts.count > 0
        x: 0; y: tl.rowsTop; width: tl.labelWidth; height: Theme.rowDense; z: 2
        cursorShape: Qt.PointingHandCursor
        onClicked: { picker.entries = backend.layers.filter(r => r.row === "layer")
                         .map(r => ({ value: r.id, label: " ".repeat(r.depth) + r.label })); picker.open() }
        Chevron { anchors { right: parent.right; rightMargin: Theme.gap; verticalCenter: parent.verticalCenter } }
        Menu { id: picker; y: parent.height; width: tl.labelWidth; onPicked: (id) => backend.select(id) }
    }
    EmptyHint {     // the kit's empty state (INTERACTION.md 1.16): gone with the first layer (2D has none: it never has no rows)
        visible: tl.emptyText !== "" && backend.rowFacts.count === 0
        x: Theme.pad; y: tl.rowsTop + Theme.gap * 2; width: tl.width - 2 * Theme.pad
        text: tl.emptyText
    }
    Item { id: overlayBox; anchors.fill: parent }   // where `overlay` lies
    Repeater {   // the project's shared markers, a faint line across every row (their flags are on the ruler)
        model: backend.markers
        delegate: Rectangle {
            required property var modelData
            x: ruler.x + Math.round(ruler.xOf(modelData.at)); y: ruler.y + ruler.height
            width: 1; height: tl.height - y - Theme.gap; color: Theme.warn; opacity: 0.35
        }
    }
    EaseList {   // a key's right-click: the one ease list, as the Key block's Ease opens it (backend.keyBar)
        id: easeMenu
        objectName: "keyEaseMenu"
        eases: backend.keyBar.easeList
        onPicked: (v) => backend.keyBar.setEase(v)
        onHovered: (v) => { if (backend.keyBar.preview) backend.keyBar.preview(v) }     // 2D plays it; 3D has no preview
    }
    Connections {
        target: backend.keyBar
        function onMenuAsked(gx, gy) {
            const p = tl.mapFromItem(null, gx, gy)
            easeMenu.current = backend.keyBar.ease || ""
            easeMenu.x = Math.min(p.x, tl.width - easeMenu.width); easeMenu.y = Math.max(0, p.y - easeMenu.implicitHeight)
            easeMenu.open()
        }
    }
    Rectangle {  // the playhead line, across every row
        x: ruler.x + Math.round(ruler.xOf(backend.time)); y: ruler.y + ruler.height
        width: 1; height: tl.height - y - Theme.gap; color: Theme.accent; opacity: 0.8
    }
    DragLabel {  // "+6 f · drop" beside the dragged edge or key, on its layer's row (time_snap.py); no row shown: under the ruler
        readonly property real mid: tl.rows && rowsBox.visible && backend.timeSnap.text !== "" ? tl.rows.rowMid(backend.timeSnap.row) : -1
        text: backend.timeSnap.text
        at: Qt.point(ruler.x + ruler.xOf(backend.timeSnap.t), mid >= 0 ? rowsBox.y + mid : ruler.y + ruler.height + 12)
    }
    SnapLine {   // what a time drag caught (a marker, key, bar end, beat, the playhead), only while snapped (time_snap.py)
        visible: backend.timeSnap.caught
        x: ruler.x + Math.round(ruler.xOf(backend.timeSnap.caughtT)); y: ruler.y + ruler.height
        width: 1; height: tl.height - y - Theme.gap
    }
}
