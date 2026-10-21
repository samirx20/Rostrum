import QtQuick
import "."

// A small sideways level meter: `value` 0..1 fills from the left, green, then amber over `warnAt`, then red over
// `dangerAt`; `peak` (0..1) is a thin mark that holds the highest recent level. Nothing here decides the units:
// the caller maps dB or amplitude to 0..1.
Item {
    id: m
    property real value: 0
    property real peak: 0
    property real warnAt: 0.7
    property real dangerAt: 0.9
    implicitWidth: 120; implicitHeight: Theme.grid * 2

    function colorAt(x) { return x >= dangerAt ? Theme.danger : x >= warnAt ? Theme.warn : Theme.ok }
    function clamp(x) { return Math.max(0, Math.min(1, x)) }

    Rectangle { anchors.fill: parent; radius: height / 2; color: Theme.sunken }
    Item {
        anchors.fill: parent; clip: true
        // three stretches, each only as far as the level reaches (the colour is by position, so a loud level shows all three)
        Rectangle { x: 0; width: m.width * Math.min(m.clamp(m.value), m.warnAt); height: parent.height; color: Theme.ok }
        Rectangle { x: m.width * m.warnAt; height: parent.height; color: Theme.warn
                    width: m.width * Math.max(0, Math.min(m.clamp(m.value), m.dangerAt) - m.warnAt) }
        Rectangle { x: m.width * m.dangerAt; height: parent.height; color: Theme.danger
                    width: m.width * Math.max(0, m.clamp(m.value) - m.dangerAt) }
        Rectangle { visible: m.peak > 0; width: 2; height: parent.height; color: m.colorAt(m.clamp(m.peak))
                    x: Math.min(m.width - width, m.width * m.clamp(m.peak)) }
    }
}
