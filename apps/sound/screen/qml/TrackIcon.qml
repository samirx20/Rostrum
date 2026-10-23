import QtQuick
import RostrumKit

// The small picture of what a track holds, drawn (no image files): "notes" a keyboard, "drums" a drum, "audio" a
// waveform, "voice" a microphone; "empty" draws nothing (the space stays, so the names line up).
Canvas {
    id: c
    property string icon: "empty"
    property color ink: Theme.fg2
    width: 14; height: 14
    onIconChanged: requestPaint()
    onInkChanged: requestPaint()
    onPaint: {
        var g = getContext("2d"); g.reset()
        g.strokeStyle = ink; g.fillStyle = ink; g.lineWidth = 1.2; g.lineCap = "round"
        if (icon === "notes") {               // three white keys, two black ones
            g.strokeRect(1.5, 2.5, 11, 9)
            g.beginPath(); g.moveTo(5.2, 7); g.lineTo(5.2, 11.5); g.moveTo(8.8, 7); g.lineTo(8.8, 11.5); g.stroke()
            g.fillRect(4, 2.5, 2.4, 5); g.fillRect(7.6, 2.5, 2.4, 5)
        } else if (icon === "drums") {        // a drum seen from the side: its skin, its shell
            g.beginPath(); g.ellipse(1.5, 2.5, 11, 4); g.stroke()
            g.beginPath(); g.moveTo(1.5, 4.5); g.lineTo(1.5, 10); g.moveTo(12.5, 4.5); g.lineTo(12.5, 10); g.stroke()
            g.beginPath(); g.moveTo(1.5, 10); g.quadraticCurveTo(7, 14, 12.5, 10); g.stroke()
        } else if (icon === "audio") {        // a short waveform
            var hs = [4, 9, 12, 6, 9]
            g.beginPath()
            for (var i = 0; i < hs.length; i++) { var x = 2 + i * 2.5; g.moveTo(x, 7 - hs[i] / 2); g.lineTo(x, 7 + hs[i] / 2) }
            g.stroke()
        } else if (icon === "voice") {       // a microphone on its stand
            g.beginPath(); g.roundedRect(4.5, 0.8, 5, 8, 2.5, 2.5); g.fill()
            g.beginPath(); g.moveTo(2.5, 6.5); g.quadraticCurveTo(2.5, 11, 7, 11); g.quadraticCurveTo(11.5, 11, 11.5, 6.5); g.stroke()
            g.beginPath(); g.moveTo(7, 11); g.lineTo(7, 13.2); g.moveTo(4.5, 13.2); g.lineTo(9.5, 13.2); g.stroke()
        }
    }
}
