import QtQuick
import RostrumKit

// The header's Render (F12): one click starts the Final picture of the shot's current frame (render_job.py); the ▾
// beside it opens the render sheet (a video of the shot, another quality or size, EXR; Ctrl+E). While a render runs,
// the same two places show it: the Render button's place fills as the seconds pass against the time it said ("12 / 40 s";
// the whole sentence on hover and in the top bar), the ▾'s place is Cancel. Both states have the same width, so nothing
// moves under the pointer (a second click on Render lands on the progress, which does nothing).
Item {
    id: rb
    readonly property var job: backend.renderJob
    readonly property bool running: job.state === "running"
    implicitWidth: 96 + 1 + 28
    implicitHeight: Theme.button

    Button {
        id: go
        objectName: "renderButton"
        visible: !rb.running
        width: 96; height: parent.height
        text: "Render"; kind: "primary"; job: "render"
        help: "The final-quality picture of this frame, saved in the project's Renders folder and shown when done."
        onClicked: rb.job.start()
    }
    Rectangle {     // running: the time so far against the time it said
        id: busy
        objectName: "renderProgress"
        visible: rb.running
        width: 96; height: parent.height; radius: Theme.radiusCtl; color: Theme.raised; clip: true
        Rectangle { width: parent.width * rb.job.progress; height: parent.height; color: Theme.accentFill; opacity: 0.55
                    Behavior on width { NumberAnimation { duration: 900 } } }
        Text { anchors.centerIn: parent; text: rb.job.clock; color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body }
        HoverHandler { id: busyHover }
        HoverTip { text: rb.job.note; hovered: busyHover.hovered }
    }
    Button {
        id: more
        objectName: "renderMore"
        visible: !rb.running
        x: go.width + 1; width: 28; height: parent.height     // a split button: one blue shape, a hairline between
        chevron: true; kind: "primary"
        tip: "More render choices"
        help: "A video of the shot, another quality or size, EXR for the Editor: the render sheet."
        onClicked: backend.exporter.openFor()
    }
    Rectangle {     // Cancel, in the ▾'s place (a kit Button's padding leaves no room for its × at this width)
        objectName: "renderCancel"
        visible: rb.running
        x: more.x; width: 28; height: parent.height; radius: Theme.radiusCtl
        color: cancelArea.pressed ? Theme.active : cancelHover.hovered ? Theme.hover : Theme.raised
        Text { anchors.centerIn: parent; text: "×"; color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body + 2 }
        HoverHandler { id: cancelHover; cursorShape: Qt.PointingHandCursor }
        HoverTip { text: "Cancel the render"; hovered: cancelHover.hovered }
        MouseArea { id: cancelArea; anchors.fill: parent; onClicked: rb.job.cancel() }
    }
}
