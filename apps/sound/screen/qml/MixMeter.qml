import QtQuick
import RostrumKit
import "MixFormat.js" as F

// A level bar from the last render's peak (dBFS) on the fader's own scale, coloured by F.levelTone (one rule for every
// strip and the master). Unmeasured: the empty sunken well, so a strip keeps its shape.
Rectangle {
    id: m
    property var peak: null            // dBFS, or null: not measured
    property string tip: ""            // the words under it while the pointer rests on it
    readonly property bool measured: peak !== null && peak !== undefined
    width: 8; radius: 2; color: Theme.sunken
    Rectangle {
        visible: m.measured
        anchors.bottom: parent.bottom; width: parent.width; radius: 2
        height: parent.height * F.posOfDb(m.measured ? m.peak : -100)
        color: Theme[F.levelTone(m.peak)]
    }
    HoverHandler { id: hover }
    HoverTip { text: m.tip; hovered: hover.hovered }
}
