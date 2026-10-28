import QtQuick
import RostrumKit

// The live 3D viewport: Storm drawn inside the window (Look: Quick; LiveView.qml, or the engine's picture in offscreen
// runs), or progressive Cycles in place with the Render button's settings (Look: Final, Shift+F; a thin line along the
// bottom shows how far it has got) (image://view, drawn off the GUI thread at this item's size),
// (its viewport-only settings live in the Scene panel, ScenePanel.qml). A right drag turns the view in every tool (a
// right click, press and release without moving, opens the menu); a left drag on empty space turns it too where the
// tool gives the left drag no other job (Select, the clay brushes off the clay, Pose off the clay; never while Draw,
// Spin, Paint or Edit mesh's box take it). Middle drag or Shift + left drag pans, the wheel zooms; on a touchpad two
// fingers turn the view and a pinch zooms (screen3d/view_input.py). A click selects what is there, a double click goes
// home. In the shot camera, or looking through a light, any camera move continues freely from its view. Resting on
// Make this the shot draws the shot's frame in the free view. None of this touches the document or its history.
Rectangle {
    id: vp
    objectName: "viewport3d"
    color: Theme.sunken
    radius: Theme.radiusCtl
    clip: true
    readonly property real dpr: Screen.devicePixelRatio
    readonly property bool free: viewport.mode === "free"
    readonly property bool throughLight: viewport.mode === "light"
    readonly property bool final: viewport.look === "final"
    // the pointer over the view: while a drag turns it, the move arrows; while it pans, the closed hand; a shape (or
    // Lump) waiting for its click, the cross; else the arrow (Qt's own shapes until the kit's turn / grab pointers
    // land). The layers above that cover the view (Gizmo) show it where they have nothing of their own
    readonly property int pointer: rightArea.pressed && rightArea.dragged ? Qt.SizeAllCursor
                                   : viewArea.pressed && viewArea.dragged ? (viewArea.panning ? Qt.ClosedHandCursor : Qt.SizeAllCursor)
                                   : backend.adder.armed || viewport.clay.tool === "lump" && viewport.clay.on ? Qt.CrossCursor : Qt.ArrowCursor

    // a wheel event, from any layer of the view: a mouse wheel (and Ctrl + wheel, a Windows touchpad's pinch) zooms, a
    // touchpad's two-finger scroll turns (view_input.py)
    function wheel(w) {
        const pad = w.device !== undefined && w.device !== null && w.device.type === PointerDevice.TouchPad
        viewport.wheel(w.angleDelta.x, w.angleDelta.y, w.pixelDelta.x, w.pixelDelta.y, w.phase !== Qt.NoScrollPhase,
                       (w.modifiers & Qt.ControlModifier) !== 0, pad)
    }
    function resize() { if (width > 0 && height > 0) viewport.setSize(width * dpr, height * dpr) }
    onWidthChanged: resize()
    onHeightChanged: resize()
    Component.onCompleted: resize()

    Loader {   // the live view drawn in the window itself (LiveView.qml); offscreen pictures and Final use the Image
        anchors.fill: parent
        active: viewport.inWindow
        visible: !vp.final
        source: "LiveView.qml"
    }
    Image {
        anchors.fill: parent
        visible: !viewport.inWindow || vp.final
        source: visible && viewport.pictureSerial > 0 ? "image://view/" + viewport.pictureSerial : ""
        cache: false; smooth: true
    }

    DropArea {  // a material ball dragged from the picker or the Materials list: the item under the pointer gets it
        anchors.fill: parent; keys: ["rostrum-material"]
        onDropped: (d) => { viewport.dropMaterial(d.source.materialId, d.x * vp.dpr, d.y * vp.dpr); d.accept() }
    }
    ImportDrop { anchors.fill: parent; z: 12 }   // a file from Explorer: lands where it is dropped (importing.py)
    Item {   // the shot frame (shot camera, or the free view while Make this the shot is hovered): the scene outside it
             // dimmed, a thin edge
        id: frame
        objectName: "shotFrame"
        visible: viewport.mode === "shot" || viewport.previewShot
        readonly property var r: viewport.frameRect
        x: r[0] * vp.width; y: r[1] * vp.height; width: r[2] * vp.width; height: r[3] * vp.height
        readonly property color shade: Qt.rgba(0, 0, 0, viewport.dim ? 0.65 : 0)
        Rectangle { color: frame.shade; x: -frame.x; y: -frame.y; width: vp.width; height: frame.y }
        Rectangle { color: frame.shade; x: -frame.x; y: frame.height; width: vp.width; height: vp.height - frame.y - frame.height }
        Rectangle { color: frame.shade; x: -frame.x; y: 0; width: frame.x; height: frame.height }
        Rectangle { color: frame.shade; x: frame.width; y: 0; width: vp.width - frame.x - frame.width; height: frame.height }
        Rectangle { anchors.fill: parent; color: "transparent"; border.width: 1; border.color: Theme.popupEdge }
    }

    ContextMenu3D { id: ctx }
    function openContext(id) { ctx.openAt(vp, width / 2, height / 2, id) }   // (the scripted `context` step)
    TurnArea {       // right drag: turn the view (every tool); right click: pick what is under the pointer, then the menu
                     // for it (the pick answers later). Pose takes its own right button (Pose.qml: the same two)
        id: rightArea
        objectName: "viewRightArea"
        anchors.fill: parent
        property bool pending: false
        onTurned: (dx, dy) => viewport.orbit(dx, dy)
        onRightClicked: (x, y) => {
            if (backend.adder.armed) return backend.adder.disarm()   // a right-click lets go of the shape waiting to be placed
            backend.rightClickStarts(); pending = true; viewport.rightClick(x * vp.dpr, y * vp.dpr)   // the menu opens at (px, py); the floor = empty space
        }
        Connections {
            target: viewport
            function onPicked(id) {
                if (!rightArea.pending) return
                rightArea.pending = false
                ctx.openAt(vp, rightArea.px, rightArea.py, id)
            }
        }
    }

    MouseArea {
        id: viewArea
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton | Qt.MiddleButton
        preventStealing: true
        property real lx: 0
        property real ly: 0
        property real sx: 0
        property real sy: 0
        property bool dragged: false
        property bool panning: false
        onPressed: (m) => {
            lx = sx = m.x; ly = sy = m.y; dragged = false
            panning = (m.button === Qt.MiddleButton && !meshEdit.on && !paintMode.on) || (m.modifiers & Qt.ShiftModifier)   // Edit mesh, Paint: middle orbits
        }
        onPositionChanged: (m) => {
            dragged = dragged || Math.abs(m.x - sx) + Math.abs(m.y - sy) > 3
            if (!dragged) return
            var dx = m.x - lx, dy = m.y - ly
            lx = m.x; ly = m.y
            if (panning) viewport.pan(dx * vp.dpr, dy * vp.dpr)
            else viewport.orbit(dx, dy)
        }
        onReleased: (m) => {
            if (dragged || m.button !== Qt.LeftButton) return
            if (m.modifiers & Qt.AltModifier) viewport.altClick(m.x * vp.dpr, m.y * vp.dpr)   // place the light's highlight
            else viewport.click(m.x * vp.dpr, m.y * vp.dpr)
        }
        onDoubleClicked: (m) => { if (m.button === Qt.LeftButton && viewport.hasShot) viewport.home() }
        onWheel: (w) => vp.wheel(w)
        cursorShape: vp.pointer
    }
    PinchHandler {   // a pinch (touchpad gesture or two fingers on a touch screen) zooms; the view itself never scales
        target: null
        rotationAxis.enabled: false
        onScaleChanged: (delta) => viewport.pinch(delta)
    }
    // the viewport's drawn layers, each its own (z), the gizmo on top: a press it doesn't take falls through
    PaintStrokes { anchors.fill: parent; z: 9 }   // Paint: a left drag paints on the mesh; its trail and the brush disc
    // Clay: a left drag sculpts the clay (or turns the view off it); the brush ring. Above the gizmo: the gizmo's area
    // takes every hover move under it (so the ring never showed and F had nothing to size), and while Clay is on the
    // gizmo has no handles; Clay off, this layer is hidden
    ClayStrokes { anchors.fill: parent; z: 11.2 }
    ClayDraw { anchors.fill: parent; z: 11.3; d: viewport.clay.drawObj }   // Clay's Draw, Spin: a left drag draws
    // Pose: a left drag on the clay poses it, a click holds a spot; its bones, joints and holds (Pose off: hidden)
    Pose { anchors.fill: parent; z: 11.4; onMenuAt: (x, y) => ctx.openAt(vp, x, y, backend.selected) }
    MeshEdit { anchors.fill: parent; z: 10 }  // Edit mesh: the edges, the picked points / edges / faces, the extrude arrow
    Bones { anchors.fill: parent; z: 10.5 }  // a mesh's bone chain (Animate) and the points Bones is placing; draws only
    Gizmo { anchors.fill: parent; z: 11 }   // the selected item's handles; a press off them falls through to the area above
    TypeInPlace { }                  // a 3D text just placed: its cursor where it landed, typing changes the words

    Rectangle {  // the Final look's progress: a thin line along the bottom edge
        visible: vp.final
        anchors { left: parent.left; bottom: parent.bottom }
        width: parent.width * Math.max(0, Math.min(1, viewport.finalFraction)); height: 2
        color: Theme.accent
    }
    Text {  // how far Final has got ("Final · 64 of 128 samples · 12 s"), in place of the movement hints
        visible: vp.final
        anchors { left: parent.left; bottom: parent.bottom; margins: Theme.pad }
        text: viewport.finalLine
        color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label
    }
    Text {  // which light is looked through
        visible: vp.throughLight && !vp.final
        anchors { left: parent.left; bottom: parent.bottom; margins: Theme.pad }
        text: "Through light " + viewport.throughLight + "  ·  where it shines is the middle  ·  drag to look around freely"
        color: Theme.fg4; font.family: uiFont; font.pixelSize: Theme.label
    }
    Text {  // how to move, only while the free camera is in use
        visible: vp.free && !vp.final
        anchors { left: parent.left; bottom: parent.bottom; margins: Theme.pad }
        text: "Free camera  ·  right-drag to turn  ·  Shift-drag to pan  ·  scroll to zoom" + (viewport.hasShot ? "  ·  ` back to the shot" : "")
        color: Theme.fg4; font.family: uiFont; font.pixelSize: Theme.label
    }
    Rectangle {  // a changed clay being built again (an undo of a stroke): the view shows the clay from before meanwhile
        objectName: "clayUpdating"
        visible: viewport.rebuilding
        anchors { top: parent.top; horizontalCenter: parent.horizontalCenter; topMargin: Theme.pad }
        width: updatingText.implicitWidth + 2 * Theme.pad; height: Theme.rowDense; radius: height / 2
        color: Theme.raised
        Text { id: updatingText; anchors.centerIn: parent; text: "Updating the clay…"
               color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.label }
    }
    Text {  // a failure says so, in place
        visible: viewport.status !== ""
        anchors { right: parent.right; bottom: parent.bottom; margins: Theme.pad }
        width: Math.min(implicitWidth, parent.width - 2 * Theme.pad)
        horizontalAlignment: Text.AlignRight; wrapMode: Text.Wrap
        text: viewport.status
        color: viewport.status.startsWith("Error") ? Theme.danger : Theme.fg3
        font.family: uiFont; font.pixelSize: Theme.label
    }
}
