import QtQuick
import RostrumKit

// A row's "A" (automation) button, in its header beside R / M / S (never over the notes): opens and closes the
// automation lane under the row (volume, pan, a send's level …). A dot in its corner says the row already holds
// automation; tinted while the lane is open.
HeaderButton {
    id: t
    property var track
    letter: "A"
    lit: !!track.auto
    soft: true
    dot: !!track.autoUsed
    dotColor: track.hue
    tip: lit ? "Close the automation lane" : "Automation: draw volume, pan and more changing over time"
    onClicked: backend.toggleLanes(t.track.id)
}
