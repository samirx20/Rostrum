import QtQuick
import RostrumKit
import "MixFormat.js" as F

// A level bar from the last render's peak (dBFS) on the fader's own scale. Absent (not zero) without a measurement.
Rectangle {
    id: m
    property var peak: null            // dBFS, or null: not measured
    visible: peak !== null && peak !== undefined
    width: 6; radius: 3; color: Theme.sunken
    Rectangle {
        anchors.bottom: parent.bottom; width: parent.width; radius: 3
        height: parent.height * F.posOfDb(m.peak === null ? -100 : m.peak)
        color: m.peak > 0 ? Theme.danger : m.peak > -6 ? Theme.warn : Theme.ok
    }
}
