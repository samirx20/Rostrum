import QtQuick
import RostrumKit
import "MixFormat.js" as F

// The fader's dB scale: a tick and a number per mark of F.SCALE, placed with F.posOfDb on the same travel as the
// fader (`inset` = half its knob at each end), so 0 on the scale is exactly where the knob sits at 0 dB.
Item {
    id: sc
    property real inset: 7
    readonly property real travel: height - 2 * inset
    implicitWidth: 22
    // a number only where it has room: 0, −∞ and −24 first, then the rest while a number's own height clear
    // of every number shown (`room`: measured, so no two numbers ever touch);
    // every mark keeps its tick
    TextMetrics { id: digits; font.family: uiFont; font.pixelSize: Theme.label - 1; text: "−48" }
    readonly property real room: Math.ceil(digits.height) + 1          // a whole line of text, as drawn
    readonly property var shown: {
        var order = [1, 6, 4, 5, 0, 3, 2], ys = [], out = F.SCALE.map(() => false)
        for (var k = 0; k < order.length; k++) {
            var y = travel * (1 - F.posOfDb(F.SCALE[order[k]]))
            if (ys.every(v => Math.abs(v - y) >= sc.room)) { ys.push(y); out[order[k]] = true }
        }
        return out
    }
    Repeater {
        model: F.SCALE
        delegate: Item {
            required property var modelData
            required property int index
            width: sc.width; height: 10
            y: sc.inset + sc.travel * (1 - F.posOfDb(modelData)) - height / 2
            Text {
                anchors.right: tick.left; anchors.rightMargin: 2; anchors.verticalCenter: parent.verticalCenter
                visible: sc.shown[index]
                text: F.scaleText(modelData); color: modelData === 0 ? Theme.fg2 : Theme.fg3
                font.family: uiFont; font.pixelSize: Theme.label - 1; font.features: { "tnum": 1 }
            }
            Rectangle { id: tick; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                        width: 3; height: 1; color: Theme.fg4 }
        }
    }
}
