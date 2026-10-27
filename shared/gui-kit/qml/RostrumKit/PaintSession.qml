pragma Singleton
import QtQuick

// The fill picker open right now, for on-canvas handles (GradientHandles): `field` is the PaintField whose picker is
// open (null when none). `paint` is what it shows (live while it changes), `selected` its picked stop; `gradient`:
// open on a linear, radial or angular fill. A PaintField sets and clears `field` as its picker opens and closes.
// `hold`: the pointer is over the handles, so a press there doesn't close the picker (the host sets it on hover).
QtObject {
    property Item field: null
    property bool hold: false
    property rect area: Qt.rect(0, 0, 0, 0)     // the open picker's place in the window (the field sets it): handles keep out from under it
    readonly property var paint: field ? field.cur : null
    readonly property int selected: field ? field.stop : -1
    readonly property bool gradient: !!paint && ["linear", "radial", "angular"].indexOf(paint.type) >= 0
}
