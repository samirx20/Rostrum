pragma Singleton
import QtQuick

// Where the pointer last pressed (window px), shared by every HoverTip. A click often moves the screen (a sheet opens,
// a chip slides over); the pointer has not moved, but another control is now under it and would show its tip on top of
// what the click opened. A tip stays away until the pointer has moved a few pixels from its last press.
QtObject {
    property point at: Qt.point(-1000, -1000)       // where the pointer is now (window px), from one hover handler per window
    property point pressAt: Qt.point(-1000, -1000)
    property var tracked: []
    property Component tracker: Component { HoverHandler { blocking: false; onPointChanged: TipGate.at = point.scenePosition } }
    // One handler on the window's root item, not one over each control: an item that takes hover (a HoverHandler's
    // item) hides every MouseArea under it from hover, so a tip's own layer made its control stop being hovered.
    function track(win) { if (win && tracked.indexOf(win) < 0) { tracked.push(win); tracker.createObject(win.contentItem) } }
    function near(at) { return Math.abs(at.x - pressAt.x) < 4 && Math.abs(at.y - pressAt.y) < 4 }
}
