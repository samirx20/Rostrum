import QtQuick
import "."

// A thin, calm scroll bar for a Flickable: only there while the content is taller than the view, faint at rest,
// a little brighter while scrolling. Not draggable (the wheel and touch scroll); it sits in the margin just right of the Flickable.
Item {
    id: bar
    property Flickable flick
    readonly property bool needed: flick && flick.contentHeight > flick.height + 1
    width: Theme.scrollWidth
    anchors { right: flick ? flick.right : undefined; rightMargin: -Theme.grid; top: flick ? flick.top : undefined; bottom: flick ? flick.bottom : undefined }
    visible: needed

    Rectangle {
        width: parent.width; radius: width / 2
        height: bar.needed ? Math.max(Theme.field, bar.height * bar.flick.height / bar.flick.contentHeight) : 0
        y: bar.needed ? (bar.height - height) * bar.flick.contentY / Math.max(1, bar.flick.contentHeight - bar.flick.height) : 0
        color: bar.flick && bar.flick.moving ? Theme.fg : Theme.fg2
        Behavior on color { ColorAnimation { duration: Theme.fast } }
    }
}
