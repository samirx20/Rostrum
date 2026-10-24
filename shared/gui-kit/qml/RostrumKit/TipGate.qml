pragma Singleton
import QtQuick

// Where the pointer last pressed (window px), shared by every HoverTip. A click often moves the screen (a sheet opens,
// a chip slides over); the pointer has not moved, but another control is now under it and would show its tip on top of
// what the click opened. A tip stays away until the pointer has moved a few pixels from its last press.
QtObject {
    property point pressAt: Qt.point(-1000, -1000)
    function near(at) { return Math.abs(at.x - pressAt.x) < 4 && Math.abs(at.y - pressAt.y) < 4 }
}
