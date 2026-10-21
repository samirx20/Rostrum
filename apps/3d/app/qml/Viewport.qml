import QtQuick
import RostrumKit

// The live 3D viewport: the engine's Storm picture (image://view, drawn off the GUI thread at this item's size),
// with a small bar of viewport-only settings. Left drag orbits, middle drag or Shift + left drag pans, the wheel
// zooms, a click (press and release without dragging) selects what is there, a double click goes home. In the shot
// camera any camera move continues freely from its view. None of this touches the document or its history.
Rectangle {
    id: vp
    color: Theme.sunken
    radius: Theme.radiusCtl
    clip: true
    readonly property real dpr: Screen.devicePixelRatio
    readonly property bool free: viewport.mode === "free"

    function resize() { if (width > 0 && height > 0) viewport.setSize(width * dpr, height * dpr) }
    onWidthChanged: resize()
    onHeightChanged: resize()
    Component.onCompleted: resize()

    Image {
        anchors.fill: parent
        source: viewport.serial > 0 ? "image://view/" + viewport.serial : ""
        cache: false; smooth: true
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
            panning = m.button === Qt.MiddleButton || (m.modifiers & Qt.ShiftModifier)
        }
        onPositionChanged: (m) => {
            dragged = dragged || Math.abs(m.x - sx) + Math.abs(m.y - sy) > 3
            if (!dragged) return
            var dx = m.x - lx, dy = m.y - ly
            lx = m.x; ly = m.y
            if (panning) viewport.pan(dx * vp.dpr, dy * vp.dpr)
            else viewport.orbit(dx, dy)
        }
        onReleased: (m) => { if (!dragged && m.button === Qt.LeftButton) viewport.click(m.x * vp.dpr, m.y * vp.dpr) }
        onDoubleClicked: (m) => { if (m.button === Qt.LeftButton && viewport.hasShot) viewport.home() }
        onWheel: (w) => viewport.zoom(w.angleDelta.y / 120)
    }

    Rectangle {  // the viewport-only settings
        id: bar
        anchors { top: parent.top; right: parent.right; margins: Theme.gap }
        width: row.implicitWidth + 2 * Theme.gap; height: Theme.button + Theme.gap
        radius: Theme.radiusCtl; color: Theme.panel; border.width: 1; border.color: Theme.popupEdge
        MouseArea { anchors.fill: parent }   // clicks on the bar never pick through it

        Row {
            id: row
            anchors.centerIn: parent
            spacing: Theme.gap
            component Label: Text {
                anchors.verticalCenter: parent.verticalCenter
                color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.label
            }

            Label { text: "Shot camera"; visible: viewport.hasShot }
            Toggle {
                visible: viewport.hasShot
                anchors.verticalCenter: parent.verticalCenter
                checked: !vp.free
                onToggled: (v) => viewport.setMode(v ? "shot" : "free")
            }
            Label { text: "Exposure" }
            Slider {
                width: 96; anchors.verticalCenter: parent.verticalCenter
                from: -4; to: 4; step: 0.1; value: viewport.exposure
                onScrubbed: (v) => viewport.setExposure(v)
                onEdited: (v) => viewport.setExposure(v)
            }
            Label { text: "Studio light"; visible: viewport.studioInUse }
            Slider {
                visible: viewport.studioInUse   // the scene's own dome lights the view: the studio isn't used
                width: 96; anchors.verticalCenter: parent.verticalCenter
                from: 0; to: 2; step: 0.05; value: viewport.studio
                onScrubbed: (v) => viewport.setStudio(v)
                onEdited: (v) => viewport.setStudio(v)
            }
            Label { text: "Scene lights" }
            Toggle {
                anchors.verticalCenter: parent.verticalCenter
                checked: viewport.sceneLights
                onToggled: (v) => viewport.setSceneLights(v)
            }
            Button {
                visible: vp.free && viewport.hasShot
                anchors.verticalCenter: parent.verticalCenter
                kind: "ghost"; text: "Home"
                onClicked: viewport.home()
            }
        }
    }

    Text {  // how to move, only while the free camera is in use
        visible: vp.free
        anchors { left: parent.left; bottom: parent.bottom; margins: Theme.pad }
        text: "Drag to orbit  ·  Shift-drag to pan  ·  Scroll to zoom"
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
