import QtQuick
import "."

// A soft edge for a scrolling panel: where there is more to scroll to, the last `size` px of the Flickable fade into the
// panel's colour, so a half-scrolled row dissolves instead of leaving a stray mark (S36: the top 5 px of the next group's
// header showed as a "." above "Last changed by"). Laid over the Flickable: `EdgeFade { flick: scroller; anchors.fill: scroller }`.
// `color` is what the panel behind is painted with (Theme.panel). It never takes a click. The layout check
// (layout_check.stray) treats a sliver under an item of this type as fine.
Item {
    id: fade
    property Flickable flick
    property color color: Theme.panel
    property int size: 2 * Theme.row  // two rows: a half-cut row reads as fading, not cut
    enabled: false                 // no mouse: the wheel and clicks reach the rows under it
    Rectangle {
        visible: fade.flick && fade.flick.contentY > 1
        anchors { left: parent.left; right: parent.right; top: parent.top }
        height: fade.size
        gradient: Gradient {
            GradientStop { position: 0; color: fade.color }
            GradientStop { position: 1; color: Qt.alpha(fade.color, 0) }
        }
    }
    Rectangle {
        visible: fade.flick && !fade.flick.atYEnd
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
        height: fade.size
        gradient: Gradient {
            GradientStop { position: 0; color: Qt.alpha(fade.color, 0) }
            GradientStop { position: 1; color: fade.color }
        }
    }
}
