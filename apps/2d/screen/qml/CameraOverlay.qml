import QtQuick

// The Camera tool over the canvas (screen2d/camera_tool.py does the work): drag pans the camera, Alt+drag pushes in
// (up) or out (down). Absent unless the tool is on. One drag = one change. The Stage's mapping gives composition px.
Item {
    id: ov
    property Item stage
    readonly property bool on: backend.tool === "camera" && !backend.playing

    MouseArea {
        anchors.fill: parent
        enabled: ov.on && !spaceKey.held         // Space held: the view pans (ViewInput.qml)
        visible: enabled
        cursorShape: (Qt.application.keyboardModifiers & Qt.AltModifier) ? Qt.SizeVerCursor : Qt.OpenHandCursor
        preventStealing: true
        property bool going: false
        property bool push: false           // Alt at the press: this drag zooms instead of panning
        property real sx: 0
        property real sy: 0
        onPressed: (m) => { sx = m.x; sy = m.y; push = (m.modifiers & Qt.AltModifier) !== 0; going = backend.cameraTool.begin() }
        onPositionChanged: (m) => {
            if (going) backend.cameraTool.drag((m.x - sx) / ov.stage.compScale, (m.y - sy) / ov.stage.compScale,
                                               push)
        }
        onReleased: { if (going) backend.endDrag(); going = false }
        onCanceled: { if (going) backend.endDrag(); going = false }
    }
}
