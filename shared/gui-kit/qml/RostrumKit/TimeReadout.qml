import QtQuick
import RostrumKit
import "ValueKinds.js" as VK

// The playhead as text, one format: seconds ("1.20 s"), digits all one width. The frame number and the scene's length
// are on hover. A click (or Alt+Shift+J, the window's `timeBox`) turns it into a text box with the time selected: type
// 2.5 / 2.5 s (seconds), 36f (frames), 1:12 (minutes:seconds), +12f / -0.5 (on / back from here) or a marker's name
// (#logo lands, logo lands); Enter goes there, Esc leaves it, a click elsewhere goes there. A time past the scene is
// refused in a sentence. The reading is ValueKinds.read("time", ...): one reader. While the box has the keyboard every key is its own.
Item {
    id: tr
    objectName: "timeBox"
    property bool typing: false
    z: typing ? 2 : 0                   // the open box draws over the buttons beside it
    implicitWidth: label.implicitWidth + 2 * Theme.grid
    implicitHeight: Math.max(label.implicitHeight, Theme.field)
    function ask() { typing = true; box.input.forceActiveFocus(); box.input.selectAll() }
    Component.onCompleted: { const w = Window.window; if (w && w.timeBox !== undefined) w.timeBox = tr }
    Component.onDestruction: { const w = Window.window; if (w && w.timeBox === tr) w.timeBox = null }

    Text { id: label; x: Theme.grid; anchors.verticalCenter: parent.verticalCenter; visible: !tr.typing
           text: backend.time.toFixed(2) + " s"; color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body
           font.features: { "tnum": 1 } }
    MouseArea { id: click; anchors.fill: parent; enabled: !tr.typing; hoverEnabled: true; cursorShape: Qt.IBeamCursor; onClicked: tr.ask() }
    HoverTip { hovered: click.containsMouse && !tr.typing
               text: "Frame " + Math.round(backend.time * backend.frameInfo.fps) + " · scene "
                     + (backend.frameInfo.duration || 0).toFixed(2) + " s · click to type a time" }
    FieldFrame {
        id: box
        objectName: "timeField"
        height: parent.height; visible: tr.typing; z: 1     // grows over its neighbours while a longer time or a marker's name is typed
        width: Math.min(220, Math.max(parent.width, typed.advanceWidth(box.input.text) + box.input.x + 2 * Theme.gap + 4))   // the caret and the right edge too
        FontMetrics { id: typed; font: box.input.font }     // read, not laid out: the width never feeds back into itself
        text: label.text; editable: true; keepOnRefusal: true
        onCommitted: (t) => {
            const r = VK.read("time", t, { t: backend.time, fps: backend.frameInfo.fps || 30, duration: backend.frameInfo.duration || 0,
                                           markers: backend.markers || [] })
            if (r.error) problem = r.error; else backend.setTime(r.value)
        }
        Connections { target: box.input; function onActiveFocusChanged() { if (!box.input.activeFocus) tr.typing = false } }
    }
}
