import QtQuick
import QtQuick.Shapes
import RostrumKit

// The canvas: the engine's frame at the playhead (image://frame, rendered off the GUI thread) on a neutral backdrop,
// shown through the view (CanvasView.qml: zoom and pan, screen state), with the selected layers' outlines (Handles.qml:
// a single layer also gets resize + turn handles).
// A press picks what is painted under it (screen2d/picking.py): the outermost group, or the piece once you are inside
// that group; Ctrl+press the piece itself; double-click goes one level in; Shift+click adds / removes. Dragging moves
// it (all selected layers together), snapping to the frame and the other layers (backend.snap: Ctrl pressed after the
// drag began = no snapping, Shift = straight); dragging on empty canvas draws a rubber band that selects the layers it
// touches (boxSelect, not locked ones; Shift+box adds, Ctrl+box picks the deepest pieces). One gesture = one undo step (backend.beginMove / moveBy / endDrag; an animated
// x / y gets a key at the playhead). Layers outside the frame can still be grabbed.
// With the Draw tool on, a press draws instead: one stroke = one gesture = one undo step (painter.beginStroke / strokeTo /
// endStroke). A pen reports its pressure; a mouse is 1. The onion skin lies over the drawing's box. With the Pen tool
// on, PenOverlay takes the clicks.
// View: Ctrl+wheel / pinch zooms around the pointer, wheel / Shift+wheel scroll, Space+drag or middle-drag pans;
// the keys and the "Fit · 50 % ▾" menu are ViewControls.qml. The engine draws the frame at the size shown, up to Full, and past
// Full the visible part again at the size shown (backend.setView: screen2d/shown.py; backend.sharp: screen2d/sharp.py).
Panel {
    id: panel
    objectName: "stage"                 // scripted steps reach the view through it (screen2d/view_steps.py)
    title: "Canvas"
    property bool typing: false         // a text field has the focus (Main.qml): single-letter view keys stay off
    // the tool whose options the context bar shows instead of the selection's actions ("" = the actions)
    readonly property string toolMode: backend.create.typing ? "text" : backend.tool === "pen" ? "pen"
                                     : backend.tool === "draw" ? "paint" : ""
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
    function fitAll() { view.fitAll() }
    function zoomPercent(p) { view.show(p / 100) }
    function centreOn(x, y) { view.centreOn(x, y) }
    function panBy(dx, dy) { view.panBy(dx, dy) }
    function openViewMenu() { controls.openMenu() }
    function fitSelection() {                       // F: the selection; nothing selected: everything
        const e = backend.selectionExtent()
        if (e.x0 === undefined) view.fitAll(); else view.fitBox(e.x0, e.y0, e.x1, e.y1)
    }
    onCompScaleChanged: backend.setView(compScale, Screen.devicePixelRatio)
    Component.onCompleted: { backend.setView(compScale, Screen.devicePixelRatio); settle.restart() }
    // Past Full the visible part is drawn again at the size shown (backend.sharp: screen2d/sharp.py), once the view settles.
    readonly property var visibleKey: [view.zoom, view.ox, view.oy, well.width, well.height]
    onVisibleKeyChanged: settle.restart()
    Timer {
        id: settle; interval: 150
        onTriggered: { const a = panel.inWell(0, 0), b = panel.inWell(well.width, well.height)
                       backend.sharp.setVisible(a.x, a.y, b.x, b.y, Screen.devicePixelRatio) }
    }
    headerRight: Text { text: panel.info.width + " × " + panel.info.height + "  ·  " + panel.info.fps + " fps"
                        color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label }

    Rectangle {
        id: well
        anchors.fill: parent
        radius: Theme.radiusCtl; color: Theme.sunken
        clip: true
        readonly property bool drawing: backend.tool === "draw"
        CanvasView { id: view; wellW: well.width; wellH: well.height; compW: panel.info.width || 1; compH: panel.info.height || 1 }

        Item {
            id: frame
            x: view.ox; y: view.oy
            width: panel.info.width * view.zoom; height: panel.info.height * view.zoom
            Image {
                anchors.fill: parent
                source: backend.frame > 0 ? "image://frame/" + backend.frame : ""
                cache: false; smooth: view.zoom < 2; mipmap: view.zoom < 1   // from 200 %: the export's own pixels, unblurred
            }
            Image {  // past Full: the visible part drawn again at the size shown (backend.sharp), over the enlarged frame
                readonly property var c: backend.sharp.picture
                visible: c.serial !== undefined
                x: (c.x || 0) * view.zoom; y: (c.y || 0) * view.zoom
                width: (c.w || 0) * view.zoom; height: (c.h || 0) * view.zoom
                source: c.serial ? "image://framecrop/" + c.serial : ""
                cache: false; smooth: true
            }
            Image {  // onion skin: the neighbouring drawings, tinted, over the selected drawing's box
                readonly property var b: backend.selBox
                visible: painter.onionSerial > 0 && b.w !== undefined
                x: (b.x || 0) * view.zoom; y: (b.y || 0) * view.zoom
                width: (b.w || 0) * view.zoom; height: (b.h || 0) * view.zoom
                source: painter.onionSerial > 0 ? "image://onion/" + painter.onionSerial : ""
                cache: false; smooth: true
            }
        }
        Shape {  // the frame's edge, so a dark composition still shows where it ends; dotted once zoomed or panned off Fit
            x: frame.x - 1; y: frame.y - 1
            ShapePath {
                strokeWidth: 1; fillColor: "transparent"
                strokeColor: view.fitted ? Theme.popupEdge : Theme.fg3
                strokeStyle: view.fitted ? ShapePath.SolidLine : ShapePath.DashLine; dashPattern: [2, 3]
                PathRectangle { width: frame.width + 2; height: frame.height + 2 }
            }
        }
        Item {  // the pen
            anchors.fill: parent
            visible: well.drawing
            HoverHandler {      // Alt held: the pointer picks a colour (the swatch beside it shows the colour under it)
                id: hover
                cursorShape: backend.colourPick.alt ? Qt.PointingHandCursor : Qt.CrossCursor
                onPointChanged: { const p = panel.inWell(point.position.x, point.position.y); backend.colourPick.look(p.x, p.y) }
            }
            PointHandler {
                id: pen
                acceptedButtons: Qt.LeftButton
                function at() { return panel.inWell(point.position.x, point.position.y) }
                readonly property real pressure: point.pressure > 0 ? point.pressure : 1
                property string mode: ""        // what this press does: "stroke", "lasso" (Ctrl, or Select strokes) or "move" (picked strokes)
                property point from
                onActiveChanged: {
                    var p = at()
                    if (active && backend.colourPick.alt) { backend.colourPick.pickAt(p.x, p.y); mode = "" }       // Alt: pick the colour
                    else if (active && backend.fill.on) { backend.fill.fillAt(p.x, p.y); mode = "" }                 // Fill (G): a click fills
                    else if (active && (backend.strokeSelect.armed || (Qt.application.keyboardModifiers & Qt.ControlModifier))) {
                        backend.strokeSelect.beginLasso(p.x, p.y); mode = "lasso"                                    // a lasso round strokes
                    } else if (active && backend.strokeSelect.count > 0 && backend.strokeSelect.hits(p.x, p.y)) {
                        backend.strokeSelect.beginMove(); from = p; mode = "move"                                    // picked strokes: drag moves them
                    } else if (active) {
                        backend.strokeSelect.clear()                                                                 // a press outside lets go of them
                        mode = painter.beginStroke(p.x, p.y, pressure) ? "stroke" : ""
                    } else {
                        if (mode === "stroke") painter.endStroke()
                        else if (mode === "lasso") backend.strokeSelect.endLasso()
                        else if (mode === "move") backend.strokeSelect.endMove()
                        mode = ""
                    }
                }
                onPointChanged: {
                    if (!active) return
                    var p = at()
                    if (mode === "stroke") painter.strokeTo(p.x, p.y, pressure)
                    else if (mode === "lasso") backend.strokeSelect.lassoTo(p.x, p.y)
                    else if (mode === "move") backend.strokeSelect.moveBy(p.x - from.x, p.y - from.y)
                }
            }
            StrokeOverlay {     // the lasso, the picked strokes, the colour picker's swatch
                id: strokes
                anchors.fill: parent
                fit: view.zoom; ox: view.ox; oy: view.oy
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
            property real sx: 0
            property real sy: 0
            property point b0
            property point b1
            function comp(m) { return panel.inWell(m.x, m.y) }
            function stop() { if (moving) backend.endDrag(); moving = false; band = false }
            onPressed: (m) => {
                var p = comp(m)
                deep = (m.modifiers & Qt.ControlModifier) !== 0
                var hit = backend.multi.target(p.x, p.y, deep ? "deep" : "click")
                sx = m.x; sy = m.y; band = false; moving = false
                if (hit === "") { band = true; b0 = p; b1 = p; return }                         // nothing painted: a rubber band
                if (m.modifiers & Qt.ShiftModifier) backend.multi.toggle(hit)                   // Shift+click: add / remove
                else if (!backend.multi.has(hit)) backend.multi.pick(p.x, p.y, deep ? "deep" : "click")   // else keep the selection and move it
                moving = backend.multi.has(hit) && backend.beginMove()
            }
            onDoubleClicked: (m) => { var p = comp(m); backend.multi.pick(p.x, p.y, "in") }   // one level into the group
            onPositionChanged: (m) => {
                if (moving) {
                    backend.snap.keys((m.modifiers & Qt.ControlModifier) !== 0 && !deep, (m.modifiers & Qt.ShiftModifier) !== 0)
                    backend.moveBy((m.x - sx) / view.zoom, (m.y - sy) / view.zoom)
                } else if (band) b1 = comp(m)
            }
            onReleased: (m) => {
                if (band) {
                    if (Math.abs(m.x - sx) + Math.abs(m.y - sy) < 4) backend.pickAt(b0.x, b0.y)   // a click: the composition
                    else backend.multi.boxSelect(b0.x, b0.y, b1.x, b1.y, ((m.modifiers & Qt.ShiftModifier) ? "shift " : "")
                                                 + ((m.modifiers & Qt.ControlModifier) ? "ctrl" : ""))   // Shift adds, Ctrl: the deepest pieces
                }
                stop()
            }
            onCanceled: stop()
        }
        PenOverlay {  // the pen tool and the selected path's points (not while playing: they'd lag)
            anchors.fill: parent
            visible: !backend.playing && !well.drawing && ["rect", "ellipse", "text"].indexOf(backend.tool) < 0   // one input layer per tool
            fit: view.zoom; ox: view.ox; oy: view.oy
        }
        CreateOverlay { anchors.fill: parent; stage: panel }   // R / O / T: drag a shape, click or drag and type
        Item {  // outlines of the selected layers (turned with them) and the handles of a single one; over the pen's overlay
            id: marks
            x: view.ox; y: view.oy
            visible: !backend.playing           // they follow the playhead again when it stops (playback.py)
            Repeater {
                model: backend.multi.boxes
                delegate: Handles {
                    required property var modelData
                    box: modelData; fit: view.zoom; space: marks
                    visible: !(well.drawing && backend.paintEdge.layer === modelData.id)   // painting: its true edge instead
                    editable: backend.multi.count === 1 && !well.drawing && modelData.type !== "path" && !backend.pen.on
                }
            }
            BoneOverlay { fit: view.zoom; space: marks }   // a rig in hand: its bones and joints, posing and fixing drags (rig_view.py)
            Shape {  // painting: the target's true edge, the limit its paint stays inside (backend.paintEdge, composition px)
                visible: well.drawing && backend.paintEdge.path !== ""
                scale: view.zoom; transformOrigin: Item.TopLeft
                ShapePath {
                    strokeWidth: 1.5 / view.zoom; strokeColor: Theme.accent; fillColor: "transparent"
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
            Rectangle {  // the rubber band
                visible: canvas.band && (canvas.b0.x !== canvas.b1.x || canvas.b0.y !== canvas.b1.y)
                x: Math.min(canvas.b0.x, canvas.b1.x) * view.zoom; y: Math.min(canvas.b0.y, canvas.b1.y) * view.zoom
                width: Math.abs(canvas.b1.x - canvas.b0.x) * view.zoom; height: Math.abs(canvas.b1.y - canvas.b0.y) * view.zoom
                color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.12); border.width: 1; border.color: Theme.accent
            }
            Repeater {  // what a drag snapped to: thin magenta lines, gone on release (backend.snap.lines, composition px)
                model: backend.snap.lines
                delegate: SnapLine {            // the snap magenta (SnapLine.qml)
                    required property var modelData
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
        ToolStrip { id: tools; anchors { left: parent.left; top: parent.top; margins: Theme.gap } }   // over everything on the canvas
        ViewControls {
            id: controls
            anchors { right: parent.right; bottom: parent.bottom; margins: Theme.gap }
            view: view; typing: panel.typing
            onFitSelection: panel.fitSelection()
        }
        ContextBar {   // select, then act: the kit's bar at the top-centre, clear of the tool strip (backend.actions);
                       // with Pen, Paint or typing on, that tool's options instead (ToolOptions.qml)
            hub: backend.actions
            anchors { top: parent.top; topMargin: Theme.gap; horizontalCenter: parent.horizontalCenter }
            maxWidth: well.width - 2 * (tools.width + 2 * Theme.gap)
            toolOptions: panel.toolMode !== "" ? optionsComponent : null
            dragging: canvas.pressed || backend.playing || (backend.tool !== "move" && panel.toolMode === "")
        }
        Component { id: optionsComponent; ToolOptions { mode: panel.toolMode; room: well.width - 2 * (tools.width + 2 * Theme.gap) } }
    }
    ActionMenu { id: canvasMenu; onPicked: (v) => backend.run(v) }
    // The canvas's right-click menu at (x, y) in the well's px (default: the middle of the selection, for scripts).
    function openMenu(x, y) {
        if (x === undefined) {
            const b = backend.multi.boxes[0]
            const c = b ? Qt.point(view.ox + (b.x + b.w / 2) * view.zoom, view.oy + (b.y + b.h / 2) * view.zoom)
                        : Qt.point(well.width / 2, well.height / 2)
            x = c.x; y = c.y
        }
        const p = panel.inWell(x, y)
        const entries = backend.layerMenu(backend.multi.target(p.x, p.y, "click"))
        if (!entries.length) return
        const g = well.mapToItem(null, x, y)
        canvasMenu.entries = entries
        canvasMenu.openAt(g.x, g.y)
    }
}
