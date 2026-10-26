import QtQuick
import QtQuick.Shapes
import RostrumKit
import "Mods.js" as Mods

// The canvas: the engine's world picture at the playhead (image://frame, rendered off the GUI thread) on a neutral backdrop,
// shown through the view (CanvasView.qml: zoom and pan, screen state), with the selected layers' outlines (Handles.qml:
// a single layer also gets resize + turn handles).
// A press picks what is painted under it (screen2d/picking.py): the outermost group, or the piece once you are inside
// that group; Ctrl+press the piece itself; double-click goes one level in; Shift+click adds / removes. Dragging moves
// it (all selected layers together), snapping to the frame and the other layers (backend.snap: Ctrl pressed after the
// drag began = no snapping, Shift = straight); dragging on empty canvas draws a rubber band that selects the layers it
// touches (boxSelect, not locked ones; Shift+box adds, Ctrl+box picks the deepest pieces). One gesture = one undo step (backend.beginMove / moveBy / endDrag; an animated
// x / y gets a key at the playhead). Layers outside the frame can still be grabbed.
// The frame (FrameHandles.qml, frame_drag.py): its name tab or C picks it; picked, a drag inside it moves it, its corners
// zoom it and the zones outside them turn it; its outline never catches a click.
// With the Draw tool on, a press draws instead: one stroke = one gesture = one undo step (painter.beginStroke / strokeTo /
// endStroke). A pen reports its pressure; a mouse is 1. The onion skin lies over the drawing's box. The pointer is the
// brush ring; Alt + right-drag sizes the brush. What the pen paints on shows its edge dashed. With the Pen tool on,
// PenOverlay takes the clicks.
// View: Ctrl+wheel / pinch zooms around the pointer, wheel / Shift+wheel scroll, Space+drag or middle-drag pans;
// the keys and the "Fit · 50 % ▾" menu are ViewControls.qml. The canvas is the world (camera spec § 3.1): the engine draws the
// world rectangle the view shows at the size shown, the frame's quad holding the export (backend.world: world_view.py);
// outside the frame it is dimmed (WorldFrame.qml). Look through the frame (Shift+C, LookThrough.qml): the view fitted to the
// frame, nothing outside it; what is outside can't be picked then. Playing always shows the export fitted in the well, the
// same size and place as looking through; the view itself is never touched by play, so stop shows it as it was.
// No header row (a kit Panel always reserves one): the frame's size is on its name tab (WorldFrame.qml); size and fps are in Scene settings.
Rectangle {
    id: panel
    color: Theme.panel; radius: Theme.radiusPanel; clip: true
    objectName: "stage"                 // scripted steps reach the view through it (screen2d/view_steps.py)
    property bool typing: false         // a text field has the focus (Main.qml): single-letter view keys stay off
    property real coverLeft: 0          // how far a drawer lies over this item's left edge (AppShell.overLeft): fits and the path chip keep clear of it
    // the context bar holds only what applies to picked strokes (StrokeBar.qml); no tool puts options or hints over the canvas
    readonly property bool strokesPicked: backend.tool === "draw" && backend.strokeSelect.count > 0
    readonly property var info: backend.frameInfo
    readonly property Item canvasFrame: frame      // the picture's box
    // The one mapping between composition px and this item's px (everything over the canvas uses it: the action bar,
    // the creation overlay, and Stage's own children through `view`): compScale = screen px per composition px;
    // compOrigin = where composition (0, 0) is; compView = the visible well.
    readonly property real compScale: view.zoom
    readonly property point compOrigin: { view.ox; view.oy; width; height; return well.mapToItem(panel, view.ox, view.oy) }
    readonly property rect compView: { well.width; well.height; width; height; const p = well.mapToItem(panel, 0, 0); return Qt.rect(p.x, p.y, well.width, well.height) }
    function toComp(x, y) { return Qt.point((x - compOrigin.x) / compScale, (y - compOrigin.y) / compScale) }
    function fromComp(x, y) { return Qt.point(compOrigin.x + x * compScale, compOrigin.y + y * compScale) }
    function inWell(x, y) { return Qt.point((x - view.ox) / view.zoom, (y - view.oy) / view.zoom) }   // the same, in the well
    // the view, for the keys, the menu and scripted steps (view_steps.py)
    function fitAll() { if (opened) fitPainting(); else view.fitAll(backend.frameView.fitRect()) }   // the frame where it is at the playhead
    // A painting opened on its own (OpenedPainting.qml): the view fits it (seamless: with a repeat round it), and goes
    // back to where it was when it closes
    readonly property bool opened: backend.opened.on
    property var viewBefore: null
    function fitPainting() { const i = backend.opened.info, w = i.w || 1, h = i.h || 1, room = Theme.row + 4 * Theme.gap   // under the path chip and the size above it
                             if (i.seamless) view.fitBox(-w, -h, 2 * w, 2 * h, room); else view.fitBox(0, 0, w, h, room) }
    onOpenedChanged: {
        if (opened) { viewBefore = { cx: view.cx, cy: view.cy, asked: view.asked, fitted: view.fitted }; fitPainting() }
        else if (viewBefore) { view.cx = viewBefore.cx; view.cy = viewBefore.cy; view.asked = viewBefore.asked
                               view.fitted = viewBefore.fitted; viewBefore = null }
    }
    function fitEverything() { view.fitEverything(backend.frameView.everythingRect()) }
    function zoomPercent(p) { view.show(p / 100) }
    function centreOn(x, y) { view.centreOn(x, y) }
    function panBy(dx, dy) { view.panBy(dx, dy) }
    readonly property alias look: look              // Look through the frame (the view menu, Shift+C: ViewControls.qml)
    readonly property bool lookThrough: look.on
    function setLookThrough(on) { look.set(!!on) }
    property Item viewControls: null                // the "Fit · 57 % ▾" chip, in the top bar (Main.qml)
    function openViewMenu() { viewControls.openMenu() }
    readonly property alias view: view
    function fitSelection() {                       // F: the selection; nothing selected: everything
        const e = backend.selectionExtent()
        if (e.x0 === undefined) panel.fitAll(); else view.fitBox(e.x0, e.y0, e.x1, e.y1)
    }
    onCompScaleChanged: backend.setView(compScale, Screen.devicePixelRatio)
    readonly property string sceneSize: info.width + "x" + info.height     // a string: a new frameInfo object alone is no change
    onSceneSizeChanged: Qt.callLater(panel.fitAll)  // a new scene size: the old view no longer makes sense
    Component.onCompleted: { backend.setView(compScale, Screen.devicePixelRatio); panel.fitAll(); tellVisible() }
    // The world the well shows, told at once on every view change (backend.world: world_view.py asks a new picture
    // only when the last one no longer covers it, at the size shown).
    readonly property var visibleKey: [view.zoom, view.ox, view.oy, well.width, well.height]
    onVisibleKeyChanged: Qt.callLater(tellVisible)
    function tellVisible() { const a = panel.inWell(0, 0), b = panel.inWell(well.width, well.height)
                             backend.world.setVisible(a.x, a.y, b.x, b.y, Screen.devicePixelRatio) }

    Rectangle {
        id: well
        anchors { fill: parent; margins: Theme.pad }
        radius: Theme.radiusCtl; color: Theme.sunken
        clip: true
        readonly property bool drawing: backend.tool === "draw"
        CanvasView { id: view; wellW: well.width; coverLeft: Math.max(0, panel.coverLeft - Theme.pad); wellH: well.height; compW: panel.info.width || 1; compH: panel.info.height || 1
                     dpr: Screen.devicePixelRatio }

        Item {  // world px from here: (0, 0) of the world at view.ox, oy; one world px is view.zoom screen px
            id: frame
            x: view.ox; y: view.oy
            width: panel.info.width * view.zoom; height: panel.info.height * view.zoom
            Image {  // the world picture (backend.world: world_view.py), laid at its world rectangle; panning moves it at once
                readonly property var p: backend.world.picture
                visible: p.world === true && !backend.playing && !panel.opened
                x: (p.x || 0) * view.zoom; y: (p.y || 0) * view.zoom
                width: (p.w || 0) * view.zoom; height: (p.h || 0) * view.zoom
                source: p.world === true ? "image://frame/" + p.serial : ""
                cache: false; smooth: true
            }
            OpenedPainting {   // a painting opened on its own: it and its repeats, in world px (painting_open.py)
                visible: panel.opened; zoom: view.zoom
                visibleWorld: { view.zoom; view.ox; view.oy; const a = panel.inWell(0, 0), b = panel.inWell(well.width, well.height)
                                return Qt.rect(a.x, a.y, b.x - a.x, b.y - a.y) }
            }
            Image {  // onion skin: the neighbouring drawings, tinted, over the selected drawing's box (an opened painting's own)
                readonly property var b: panel.opened ? { x: 0, y: 0, w: backend.opened.info.w, h: backend.opened.info.h } : backend.selBox
                visible: painter.onionSerial > 0 && b.w !== undefined
                x: (b.x || 0) * view.zoom; y: (b.y || 0) * view.zoom
                width: (b.w || 0) * view.zoom; height: (b.h || 0) * view.zoom
                source: painter.onionSerial > 0 ? "image://onion/" + painter.onionSerial : ""
                cache: false; smooth: true
            }
            Image {  // wet ink's settled part (screen2d/wet.py; an opened painting shows its own: OpenedPainting.qml)
                readonly property var w: painter.wet
                visible: w.drySerial > 0 && !panel.opened && w.uses.length === 0
                x: (w.dryBox.x || 0) * view.zoom; y: (w.dryBox.y || 0) * view.zoom
                width: (w.dryBox.w || 0) * view.zoom; height: (w.dryBox.h || 0) * view.zoom
                source: w.drySerial > 0 ? "image://wet/dry-" + w.drySerial : ""
                cache: false; smooth: true; asynchronous: false
            }
            Image {  // wet ink: the stroke being drawn, at once, until the frame with it saved lands (screen2d/wet.py)
                readonly property var w: painter.wet
                visible: w.serial > 0 && !panel.opened && w.uses.length === 0
                x: (w.box.x || 0) * view.zoom; y: (w.box.y || 0) * view.zoom
                width: (w.box.w || 0) * view.zoom; height: (w.box.h || 0) * view.zoom
                source: w.serial > 0 ? "image://wet/tip-" + w.serial : ""
                cache: false; smooth: true; asynchronous: false
            }
            WetUses { zoom: view.zoom }   // painting a painted fill in place: the stroke on every layer using the painting
            Item {  // wet ink on a seamless painting: where the stroke crosses its edge it shows on the other side too (wet_wrap.py), inside the element
                id: wetCopies
                readonly property var w: painter.wet
                readonly property var b: backend.selBox
                visible: w.copies.length > 0 && b.w !== undefined
                clip: true
                x: (b.x || 0) * view.zoom; y: (b.y || 0) * view.zoom
                width: (b.w || 0) * view.zoom; height: (b.h || 0) * view.zoom
                Repeater {
                    model: wetCopies.w.copies
                    delegate: Item {
                        required property var modelData
                        readonly property var w: wetCopies.w
                        Image {
                            visible: parent.w.drySerial > 0
                            x: ((parent.w.dryBox.x || 0) + parent.modelData.x - (wetCopies.b.x || 0)) * view.zoom
                            y: ((parent.w.dryBox.y || 0) + parent.modelData.y - (wetCopies.b.y || 0)) * view.zoom
                            width: (parent.w.dryBox.w || 0) * view.zoom; height: (parent.w.dryBox.h || 0) * view.zoom
                            source: parent.w.drySerial > 0 ? "image://wet/dry" + (parent.modelData.own !== undefined ? "c" + parent.modelData.own : "") + "-" + parent.w.drySerial : ""
                            cache: false; smooth: true; asynchronous: false
                        }
                        Image {
                            visible: parent.w.serial > 0
                            x: ((parent.w.box.x || 0) + parent.modelData.x - (wetCopies.b.x || 0)) * view.zoom
                            y: ((parent.w.box.y || 0) + parent.modelData.y - (wetCopies.b.y || 0)) * view.zoom
                            width: (parent.w.box.w || 0) * view.zoom; height: (parent.w.box.h || 0) * view.zoom
                            source: parent.w.serial > 0 ? "image://wet/tip" + (parent.modelData.own !== undefined ? "c" + parent.modelData.own : "") + "-" + parent.w.serial : ""
                            cache: false; smooth: true; asynchronous: false
                        }
                    }
                }
            }
        }
        Image {  // playing (spec 4.8): the export fitted in the well, as looking through fits the view (LookThrough.qml)
            readonly property var p: backend.world.picture
            visible: backend.playing && p.world === false
            anchors.fill: parent; anchors.margins: view.frameMargin
            fillMode: Image.PreserveAspectFit
            source: p.world === false ? "image://frame/" + p.serial : ""
            cache: false; smooth: true; mipmap: true
        }
        Item { anchors.fill: parent; visible: !panel.opened   // the scene's frame: not while a painting is open
               WorldFrame { id: worldFrame; view: view; through: look.on } }   // the dimmed outside, the frame's outline and name tab (frameView); the chip: below
        Item {  // the pen
            anchors.fill: parent
            visible: well.drawing
            // the brush ring: the pointer is the brush's outline at its size on screen (Brush, Eraser); [ ] and
            // Alt + right-drag size it (left-right size, up-down hardness: `sizing`), the ring staying where the drag began
            readonly property bool noErase: backend.paintTool.now === "eraser" && !painter.canErase   // nothing to erase here: the pointer says so
            readonly property bool ringTool: !backend.colourPick.alt && !noErase && (backend.paintTool.now === "brush" || backend.paintTool.now === "eraser")
            Item {
                id: ring
                visible: parent.ringTool && hover.hovered || sizing.sizingNow
                readonly property point at: sizing.sizingNow ? sizing.from : hover.point.position
                readonly property real d: Math.max(3, painter.brushNow.size * view.zoom)
                x: at.x; y: at.y
                Rectangle { x: -ring.d / 2; y: -ring.d / 2; width: ring.d; height: ring.d; radius: ring.d / 2
                            color: "transparent"; border.width: 1; border.color: Qt.rgba(1, 1, 1, 0.85)
                            Rectangle { anchors.centerIn: parent; width: parent.width + 2; height: width; radius: width / 2
                                        color: "transparent"; border.width: 1; border.color: Qt.rgba(0, 0, 0, 0.45) }
                            Rectangle { anchors.centerIn: parent; width: ring.d * Math.max(0.05, painter.brushNow.hardness); height: width
                                        radius: width / 2; visible: sizing.sizingNow; color: "transparent"; border.width: 1; border.color: Qt.rgba(1, 1, 1, 0.4) } }
                Rectangle { x: -1.5; y: -1.5; width: 3; height: 3; radius: 1.5; color: "white"; border.color: Qt.rgba(0, 0, 0, 0.5) }
            }
            DragHandler {       // Alt + right-drag: Alt is read once, as the drag starts (moves need not repeat it)
                id: sizing
                target: null
                acceptedButtons: Qt.RightButton
                property bool on: false
                readonly property bool sizingNow: active && on
                property point from
                property real size0: 0
                property real hard0: 0
                onActiveChanged: {
                    on = active && (Mods.alt(centroid) || backend.colourPick.alt)   // Alt, as paint_pick.py reads it
                    if (on) { from = centroid.pressPosition; size0 = painter.brushNow.size; hard0 = painter.brushNow.hardness }
                }
                onTranslationChanged: if (on) {
                    painter.setValue("size", Math.max(0.5, Math.min(2000, Math.round((size0 + translation.x * 2 / view.zoom) * 2) / 2)))
                    painter.setValue("hardness", Math.max(0, Math.min(1, Math.round((hard0 - translation.y / 200) * 100) / 100)))
                }
            }
            HoverHandler {      // Alt held: the pointer picks a colour (the swatch beside it shows the colour under it)
                id: hover
                cursorShape: backend.colourPick.alt ? Qt.PointingHandCursor : parent.noErase ? Qt.ForbiddenCursor
                           : parent.ringTool ? Qt.BlankCursor : Qt.CrossCursor
                onPointChanged: { const p = panel.inWell(point.position.x, point.position.y); backend.colourPick.look(p.x, p.y) }
            }
            PointHandler {
                id: pen
                acceptedButtons: Qt.LeftButton
                function at() { return panel.inWell(point.position.x, point.position.y) }
                readonly property real pressure: point.pressure > 0 ? point.pressure : 1
                property string mode: ""        // what this press does: "stroke", "lasso" (Ctrl, or Select strokes), "move" or "handle" (picked strokes)
                property point from
                onActiveChanged: {
                    var p = at()
                    if (active && backend.colourPick.alt) { backend.colourPick.pickAt(p.x, p.y); mode = "" }       // Alt: pick the colour
                    else if (active && backend.fill.on) { backend.fill.fillAt(p.x, p.y); mode = "" }                 // Fill (G): a click fills
                    else if (active && (backend.strokeSelect.armed || Mods.ctrl(point))) {
                        backend.strokeSelect.beginLasso(p.x, p.y); mode = "lasso"                                    // a lasso round strokes
                    } else if (active && backend.strokeSelect.handleAt(p.x, p.y, view.zoom) !== "") {
                        backend.strokeSelect.beginHandle(backend.strokeSelect.handleAt(p.x, p.y, view.zoom), p.x, p.y); mode = "handle"   // a corner scales, the knob turns
                    } else if (active && backend.strokeSelect.count > 0 && backend.strokeSelect.hits(p.x, p.y)) {
                        backend.strokeSelect.beginMove(); from = p; mode = "move"                                    // picked strokes: drag moves them
                    } else if (active) {
                        backend.strokeSelect.clear()                                                                 // a press outside lets go of them
                        mode = painter.beginStroke(p.x, p.y, pressure) ? "stroke" : ""
                    } else {
                        if (mode === "stroke") painter.endStroke()
                        else if (mode === "lasso") backend.strokeSelect.endLasso()
                        else if (mode === "move") backend.strokeSelect.endMove()
                        else if (mode === "handle") backend.strokeSelect.endHandle()
                        mode = ""
                    }
                }
                onPointChanged: {
                    if (!active) return
                    var p = at()
                    if (mode === "stroke") painter.strokeTo(p.x, p.y, pressure)
                    else if (mode === "lasso") backend.strokeSelect.lassoTo(p.x, p.y)
                    else if (mode === "move") backend.strokeSelect.moveBy(p.x - from.x, p.y - from.y)
                    else if (mode === "handle") backend.strokeSelect.handleTo(p.x, p.y, Mods.shift(point))
                }
            }
            StrokeOverlay {     // the lasso, the picked strokes, the colour picker's swatch
                id: strokes
                anchors.fill: parent
                fit: view.zoom; ox: view.ox; oy: view.oy
                sizing: sizing.active || (sizing.centroid.pressedButtons & Qt.RightButton) !== 0
                cover: bar.visible ? Qt.rect(bar.x, bar.y, bar.width, bar.height) : Qt.rect(0, 0, 0, 0)    // the turn knob goes below the strokes rather than under the bar
            }
        }
        MouseArea {
            id: canvas
            anchors.fill: parent
            enabled: !well.drawing
            preventStealing: true
            property bool moving: false
            property bool band: false
            property bool deep: false       // Ctrl at the press picks the deepest piece; only a later Ctrl stops snapping
            property bool unseen: false     // looking through, the press was outside the frame: nothing there is shown
            property real sx: 0
            property real sy: 0
            property point b0
            property point b1
            function comp(m) { return panel.inWell(m.x, m.y) }
            function stop() { if (moving) backend.endDrag(); moving = false; band = false; held = "" }
            function hidden(m) { return look.on && !worldFrame.inside(m.x, m.y) }
            property string held: ""        // an Alt press on a layer: a click picks behind, a drag past 4 px makes a copy (decided on the first move)
            property bool lined: false      // Alt+Shift: the same, but a click leaves the pick alone and the copy goes along a line
            function begin(hit, p, copy) {  // a layer pressed: it is what Ctrl+C, X and V act on, not keys picked before
                backend.keys.clear()
                if (!backend.multi.has(hit)) backend.multi.pick(p.x, p.y, deep ? "deep" : "click")   // else keep the selection and move it
                moving = backend.multi.has(hit) && (copy ? backend.beginCopyMove() : backend.beginMove())
            }
            onPressed: (m) => {
                var p = comp(m)
                deep = Mods.ctrl(m)
                unseen = hidden(m)
                var hit = unseen ? "" : backend.multi.target(p.x, p.y, deep ? "deep" : "click")
                sx = m.x; sy = m.y; band = false; moving = false; held = ""; lined = Mods.alt(m) && Mods.shift(m)
                if (hit === "") { band = true; b0 = p; b1 = p; return }                         // nothing painted: a rubber band
                if (Mods.alt(m)) { held = hit; return }                                          // Alt (and Shift: on a line): click or copy-drag, not yet known
                if (Mods.shift(m)) { backend.keys.clear(); backend.multi.toggle(hit) }        // Shift+click: add / remove
                else begin(hit, p, false)
            }
            onDoubleClicked: (m) => { var p = comp(m); if (hidden(m)) return; if (!backend.create.editAt(p.x, p.y)) backend.multi.pick(p.x, p.y, "in") }   // a text: type in it; else one level into the group
            onPositionChanged: (m) => {
                if (held !== "" && Math.abs(m.x - sx) + Math.abs(m.y - sy) >= 4) { const h = held; held = ""; begin(h, comp({ x: sx, y: sy }), true) }
                if (moving) {
                    backend.snap.keys(Mods.ctrl(m) && !deep, Mods.shift(m))
                    backend.moveBy((m.x - sx) / view.zoom, (m.y - sy) / view.zoom)
                } else if (band) b1 = comp(m)
            }
            onReleased: (m) => {
                if (held !== "") { const p = comp({ x: sx, y: sy }); if (!lined) { backend.keys.clear(); backend.multi.pickBehind(p.x, p.y, deep ? "deep" : "click") }; held = "" }   // Alt+click: the layer behind (Alt+Shift+click: the pick stays)
                if (band) {
                    if (Math.abs(m.x - sx) + Math.abs(m.y - sy) < 4) {                   // a click: the composition
                        if (unseen) backend.clearSelection(); else backend.pickAt(b0.x, b0.y)
                    }
                    else backend.multi.boxSelect(b0.x, b0.y, b1.x, b1.y, (Mods.shift(m) ? "shift " : "")
                                                 + (Mods.ctrl(m) ? "ctrl" : ""))   // Shift adds, Ctrl: the deepest pieces
                }
                stop()
            }
            onCanceled: stop()
        }
        Item { anchors.fill: parent; visible: !panel.opened
               FrameHandles { world: worldFrame; stage: panel } }   // the frame: its tab picks it; picked, drag inside / corners / turn zones (frame_drag.py)
        PenOverlay {  // the pen tool and the selected path's points (not while playing: they'd lag)
            anchors.fill: parent
            visible: !backend.playing && !well.drawing && ["text", "bone"].concat(backend.create.kinds.map(k => k.kind)).indexOf(backend.tool) < 0   // one input layer per tool
            fit: view.zoom; ox: view.ox; oy: view.oy
        }
        BoneTool { anchors.fill: parent; stage: panel }        // J: draw a rig's bones joint by joint (bone_tool.py)
        CreateOverlay { anchors.fill: parent; stage: panel }   // R / O / T: drag a shape, click or drag and type
        MotionPath {    // where the selection (or the frame) travels: dots per frame, key squares, handles (motion_path.py)
            anchors.fill: parent
            visible: !backend.playing && !well.drawing && !backend.pen.on && !panel.opened
            interactive: backend.tool === "move"
            noFrame: look.on
            fit: view.zoom; ox: view.ox; oy: view.oy
        }
        Item {  // outlines of the selected layers (turned with them) and the handles of a single one; over the pen's overlay
            id: marks
            x: view.ox; y: view.oy
            visible: !backend.playing && !panel.opened          // they follow the playhead again when it stops (playback.py)
            CoverBand {     // the edges the frame sees past over the piece (cover_band.py); not while looking through
                box: backend.selBox; fit: view.zoom
                visible: edges.length > 0 && box.w !== undefined && !look.on && backend.multi.count === 1 && !well.drawing
            }
            KeptRepeater {  // kept: picking another layer (or the frame, and back) moves the same outline and knobs
                id: outlines    // to it, never remakes them
                needed: backend.multi.count > 1 ? 0 : backend.multi.boxes.length   // several: one light shape below, no knobs made
                delegate: Handles {
                    required property int index
                    readonly property var modelData: backend.multi.boxes[index] || ({})
                    box: modelData; fit: view.zoom; space: marks
                    visible: index < outlines.needed && !(well.drawing && backend.paintEdge.layer === modelData.id)   // painting: its true edge instead
                             && !(backend.create.typing && backend.selected === modelData.id)   // typing: the typing box instead
                    editable: backend.multi.count === 1 && !well.drawing && backend.tool !== "bone" && !(modelData.type === "path" && backend.pen.editing) && !backend.pen.on
                }
            }
            Shape {   // several layers: their outlines as one shape (multi.outlinePath): a dark halo under the accent line, as HaloLine draws one
                id: multiOutline
                visible: backend.multi.count > 1
                scale: view.zoom; transformOrigin: Item.TopLeft
                readonly property string d: backend.multi.boxes.length >= 0 ? backend.multi.outlinePath(
                    well.drawing ? backend.paintEdge.layer : (backend.create.typing ? backend.selected : "")) : ""
                ShapePath { strokeWidth: 3 / view.zoom; strokeColor: Qt.rgba(0, 0, 0, 0.6); fillColor: "transparent"; joinStyle: ShapePath.MiterJoin; capStyle: ShapePath.RoundCap
                            PathSvg { path: multiOutline.d } }
                ShapePath { strokeWidth: 1 / view.zoom; strokeColor: Theme.accent; fillColor: "transparent"; joinStyle: ShapePath.MiterJoin; capStyle: ShapePath.RoundCap
                            PathSvg { path: multiOutline.d } }
            }
            Handles {   // several layers: one box round them all with the same knobs, acting on all together (group_slots.py)
                box: backend.multi.groupBox; fit: view.zoom; space: marks; group: true
                visible: backend.multi.count > 1
                editable: backend.multi.count > 1 && !well.drawing && backend.tool !== "bone" && !backend.pen.on
            }
            Rectangle {   // the selection rides a path: says so over the picture (the view moves with a riding camera, so no outline)
                visible: backend.multi.ride.id !== undefined && backend.multi.count === 1
                x: -view.ox + Theme.gap; y: -view.oy + Theme.gap; width: rideWords.width + 2 * Theme.gap; height: rideWords.height + Theme.gap
                radius: Theme.radiusCtl; color: Theme.accent
                Text { id: rideWords; anchors.centerIn: parent; text: backend.multi.ride.label || ""; color: "white"
                       font.family: uiFont; font.pixelSize: Theme.label }
            }
            BoneOverlay { fit: view.zoom; space: marks }   // a rig in hand: its bones and joints, posing and fixing drags (rig_view.py)
            Shape {  // painting a painted fill in place: the painting's other users, a faint dotted edge (no words on the canvas)
                visible: well.drawing && backend.paintEdge.others !== ""
                x: backend.paintEdge.othersAt.x * view.zoom; y: backend.paintEdge.othersAt.y * view.zoom
                scale: view.zoom; transformOrigin: Item.TopLeft
                ShapePath {
                    strokeWidth: 1.5 / view.zoom; strokeColor: Qt.alpha(Theme.accent, 0.6); fillColor: "transparent"   // reads on light and dark
                    strokeStyle: ShapePath.DashLine; dashPattern: [1, 2.5]
                    PathSvg { path: backend.paintEdge.others }
                }
            }
            Shape {  // painting: the target's true edge, the limit its paint stays inside (backend.paintEdge, composition px)
                visible: well.drawing && backend.paintEdge.path !== ""
                x: backend.paintEdge.at.x * view.zoom; y: backend.paintEdge.at.y * view.zoom   // the path is sent from its corner (paint_edge.py)
                scale: view.zoom; transformOrigin: Item.TopLeft
                ShapePath {     // dashed: the limit, not a selection
                    strokeWidth: 1 / view.zoom; strokeColor: Theme.accent; fillColor: "transparent"
                    strokeStyle: ShapePath.DashLine; dashPattern: [4, 3]
                    PathSvg { path: backend.paintEdge.path }
                }
            }
            Repeater {  // what an agent just changed: a 1-second outline in the agent colour (never moves the selection or the view)
                model: backend.agent.flash.filter(id => backend.rectOf(id).w !== undefined)
                delegate: ChangeOutline {
                    id: change
                    required property string modelData
                    readonly property var b: backend.rectOf(modelData)
                    x: (b.x || 0) * view.zoom; y: (b.y || 0) * view.zoom
                    width: (b.w || 0) * view.zoom; height: (b.h || 0) * view.zoom
                    transform: Rotation { origin.x: (change.b.ax || 0) * change.width; origin.y: (change.b.ay || 0) * change.height; angle: change.b.rot || 0 }
                }
            }
            Item {  // Select layer ▸: the layer the pointer rests on in the menu, outlined (what a click would pick)
                id: peek
                readonly property var b: panel.rowHover !== "" ? backend.rectOf(panel.rowHover) : ({})
                visible: b.w !== undefined
                x: (b.x || 0) * view.zoom; y: (b.y || 0) * view.zoom
                width: (b.w || 0) * view.zoom; height: (b.h || 0) * view.zoom
                transform: Rotation { origin.x: (peek.b.ax || 0) * peek.width; origin.y: (peek.b.ay || 0) * peek.height; angle: peek.b.rot || 0 }
                Rectangle { anchors.fill: parent; color: "transparent"; border.width: 2; border.color: Theme.accent }
            }
            HaloLine {  // the rubber band
                visible: canvas.band && (canvas.b0.x !== canvas.b1.x || canvas.b0.y !== canvas.b1.y)
                x: Math.min(canvas.b0.x, canvas.b1.x) * view.zoom; y: Math.min(canvas.b0.y, canvas.b1.y) * view.zoom
                width: Math.abs(canvas.b1.x - canvas.b0.x) * view.zoom; height: Math.abs(canvas.b1.y - canvas.b0.y) * view.zoom
                fillOpacity: 0.12
            }
            KeptRepeater {  // what a drag snapped to: thin magenta lines, gone on release (backend.snap.lines, composition px);
                id: snapLines   // kept: a drag's every move updates the lines in place, never remakes them
                needed: backend.snap.lines.length
                delegate: SnapLine {            // the snap magenta (SnapLine.qml)
                    required property int index
                    readonly property var modelData: backend.snap.lines[index] || ({ axis: "x", at: 0, from: 0, to: 0 })
                    visible: index < snapLines.needed
                    readonly property bool vertical: modelData.axis === "x"
                    x: vertical ? Math.round(modelData.at * view.zoom) : modelData.from * view.zoom
                    y: vertical ? modelData.from * view.zoom : Math.round(modelData.at * view.zoom)
                    width: vertical ? 1 : (modelData.to - modelData.from) * view.zoom
                    height: vertical ? (modelData.to - modelData.from) * view.zoom : 1
                }
            }
        }
        ViewInput { anchors.fill: parent; view: view }   // wheel, pinch and Space+drag move the view
        DragHandler {  // middle-drag pans (on the well itself: other buttons pass straight to the tools)
            target: null
            acceptedButtons: Qt.MiddleButton
            property vector2d was
            onActiveChanged: was = Qt.vector2d(0, 0)
            onActiveTranslationChanged: { view.panBy(activeTranslation.x - was.x, activeTranslation.y - was.y); was = activeTranslation }
        }
        TapHandler {   // right-click: an unselected layer is selected alone first, a selected one keeps the selection
            acceptedButtons: Qt.RightButton
            enabled: backend.tool === "move"
            onTapped: (ev) => panel.openMenu(ev.position.x, ev.position.y)
        }
        ViewTools { anchors.fill: parent; view: view }   // H: drag moves the view; Z: click zooms in, Alt+click out
        Item { anchors.fill: parent; visible: !panel.opened
               FrameChip { world: worldFrame; onClicked: panel.fitAll() } }
        PathChip { visible: panel.opened; x: view.coverLeft + Theme.gap; y: Theme.gap   // "Autumn menu › Paper grain", right of any drawer, its long name ending in …
                   room: well.width - x - Theme.gap }
        LookThrough { id: look; view: view }                         // "Through the frame ×", bottom-left, while on
        ContextBar {   // select, then act: the kit's bar at the top-centre (backend.actions);
                       // only while strokes are picked: what applies to them (StrokeBar.qml)
            id: bar
            hub: backend.actions
            showName: false          // the settings panel shows the name
            // one rule: just above the frame's top edge, never over it; Fit keeps this room free (view.top), a zoomed view lets it ride the well's top
            anchors { top: parent.top; horizontalCenter: parent.horizontalCenter }
            anchors.topMargin: Math.max(Theme.gap, frame.y - bar.height - Theme.gap)
            maxWidth: well.width - 2 * Theme.gap
            toolOptions: panel.strokesPicked ? strokesComponent : null
            // only a tool's options float here: the selection's actions are on right-click and Ctrl+K (SPEC 2d-design-v2
            // §1: nothing sits on the frame)
            dragging: canvas.pressed || backend.playing || !panel.strokesPicked
        }
        Component { id: strokesComponent; StrokeBar { } }
    }
    // Select layer ▸ (first row, only where two or more layers overlap: backend.multi.underMenu): a row's layer is outlined while the
    // pointer rests on it, and a click picks it
    readonly property string rowPrefix: "selectLayer_"
    property string rowHover: ""
    ActionMenu {
        id: canvasMenu
        onPicked: (v) => v.startsWith(panel.rowPrefix) ? backend.select(v.slice(panel.rowPrefix.length)) : backend.run(v)
        onRested: (v) => panel.rowHover = v.startsWith(panel.rowPrefix) ? v.slice(panel.rowPrefix.length) : ""
    }
    // The canvas's right-click menu at (x, y) in the well's px (default: the middle of the selection, for scripts).
    function openMenu(x, y) {
        if (x === undefined) {
            const b = backend.multi.boxes[0]
            const c = b ? Qt.point(view.ox + (b.x + b.w / 2) * view.zoom, view.oy + (b.y + b.h / 2) * view.zoom)
                        : Qt.point(well.width / 2, well.height / 2)
            x = c.x; y = c.y
        }
        const p = panel.inWell(x, y)
        const picked = backend.layerMenu(backend.multi.target(p.x, p.y, "click"))
        if (!picked.length) return
        const entries = backend.multi.underMenu(p.x, p.y).concat(picked)
        const g = well.mapToItem(null, x, y)
        canvasMenu.entries = entries
        canvasMenu.openAt(g.x, g.y)
    }
    // Files dragged in from the desktop: imported where they are let go (importer.dropFiles; the Import panel's one job).
    DropArea {
        id: fileDrop
        anchors.fill: parent
        keys: ["text/uri-list"]
        onEntered: (drag) => drag.accept(Qt.CopyAction)
        onDropped: (drop) => {
            const w = fileDrop.mapToItem(panel, drop.x, drop.y), p = panel.toComp(w.x, w.y)
            if (backend.importer.dropFiles(drop.urls, p.x, p.y)) drop.accept(Qt.CopyAction)
        }
    }
}
