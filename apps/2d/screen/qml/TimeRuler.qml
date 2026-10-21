import QtQuick
import RostrumKit

// The kit's Ruler in seconds, with the project's shared markers as flags; press or drag sets the time (screen state).
Ruler {
    property alias time: r.value
    id: r
    unit: "seconds"
    markers: backend.markers
    onScrubbed: (t) => backend.setTime(t)
}
