import QtQuick
import RostrumKit

// The live 3D viewport: the engine's Storm picture (Look: Quick), or progressive Cycles in place with the Render
// button's settings (Look: Final, Shift+F; a thin line along the bottom shows how far it has got) (image://view, drawn off the GUI thread at this item's size),
// (its viewport-only settings live in the Scene panel, ScenePanel.qml). Left drag orbits, middle drag or Shift + left drag pans, the wheel
// zooms, a click (press and release without dragging) selects what is there, a double click goes home. In the shot
// camera, or looking through a light, any camera move continues freely from its view. None of this touches the
// document or its history.
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

    function resize() { if (width > 0 && height > 0) viewport.setSize(width * dpr, height * dpr) }
    onWidthChanged: resize()
    onHeightChanged: resize()
    Component.onCompleted: resize()

    Image {
        anchors.fill: parent
        source: viewport.serial > 0 ? "image://view/" + viewport.serial : ""
        cache: false; smooth: true
    }

    DropArea {  // a material ball dragged from the picker or the Materials list: the item under the pointer gets it
        anchors.fill: parent; keys: ["rostrum-material"]
        onDropped: (d) => { viewport.dropMaterial(d.source.materialId, d.x * vp.dpr, d.y * vp.dpr); d.accept() }
    }
    Item {   // the shot frame (shot camera only): the scene outside it dimmed, a thin edge, the shot's name above
        id: frame
        visible: viewport.mode === "shot"
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
    MouseArea {      // right-click: pick what is under the pointer, then the menu for it (the pick answers later)
        anchors.fill: parent
        acceptedButtons: Qt.RightButton
        property real px: 0
        property real py: 0
        property bool pending: false
        onPressed: (m) => {
            if (backend.adder.armed) return backend.adder.disarm()   // a right-click lets go of the shape waiting to be placed
            px = m.x; py = m.y; pending = true; viewport.click(m.x * vp.dpr, m.y * vp.dpr)
        }
        Connections {
            target: viewport
            function onPicked(id) {
                if (!parent.pending) return
                parent.pending = false
                ctx.openAt(vp, parent.px, parent.py, id)
            }
        }
    }

    MouseArea {
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
            panning = (m.button === Qt.MiddleButton && !meshEdit.on) || (m.modifiers & Qt.ShiftModifier)   // Edit mesh: middle orbits
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
        onWheel: (w) => viewport.zoom(w.angleDelta.y / 120)
    }

    Shortcut { sequence: "Esc"; enabled: backend.adder.armed !== ""; onActivated: backend.adder.disarm() }
    HoverHandler { cursorShape: backend.adder.armed ? Qt.CrossCursor : Qt.ArrowCursor }   // a shape waits for its click
    // the viewport's two drawn layers, each its own (z), the gizmo on top: a press it doesn't take falls through
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
        text: "Free camera  ·  drag to orbit  ·  Shift-drag to pan  ·  scroll to zoom" + (viewport.hasShot ? "  ·  ` back to the shot" : "")
        color: Theme.fg4; font.family: uiFont; font.pixelSize: Theme.label
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
