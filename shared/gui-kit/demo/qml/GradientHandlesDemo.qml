import QtQuick
import QtQuick.Controls as QQC
import QtQuick.Shapes
import RostrumKit

// Look harness for GradientHandles (see gradient_handles_demo.py). The fills are drawn from the same angle / centre
// formulas the handles use, so the line can be checked against the gradient by eye. Nothing here is an app.
QQC.ApplicationWindow {
    id: win
    visible: true; width: 1646; height: 900
    color: Theme.sunken
    property var lin: ({type: "linear", angle: 60, cx: 0.5, cy: 0.5,
                        stops: [{at: 0, color: "#ff5f6d", opacity: 1}, {at: 0.45, color: "#ffc371", opacity: 1}, {at: 1, color: "#3a6df0", opacity: 1}]})
    property var rad: ({type: "radial", angle: 0, cx: 0.4, cy: 0.55,
                        stops: [{at: 0, color: "#fff3b0", opacity: 1}, {at: 1, color: "#7a3cff", opacity: 1}]})

    component Card: Item {
        id: card
        property var paint
        property int selected: 1
        property alias handles: gh
        readonly property real a: (paint.angle || 0) * Math.PI / 180
        readonly property real ddx: Math.sin(a)
        readonly property real ddy: -Math.cos(a)
        readonly property real half: (width * Math.abs(ddx) + height * Math.abs(ddy)) / 2
        readonly property var last: paint.stops[paint.stops.length - 1]
        Shape {
            anchors.fill: parent
            ShapePath {
                strokeWidth: 0
                fillGradient: LinearGradient {
                    x1: card.width / 2 - card.ddx * card.half; y1: card.height / 2 - card.ddy * card.half
                    x2: card.width / 2 + card.ddx * card.half; y2: card.height / 2 + card.ddy * card.half
                    GradientStop { position: card.paint.stops[0].at; color: card.paint.stops[0].color }
                    GradientStop { position: card.paint.stops.length > 2 ? card.paint.stops[1].at : 0.5; color: card.paint.stops.length > 2 ? card.paint.stops[1].color : card.paint.stops[0].color }
                    GradientStop { position: card.last.at; color: card.last.color }
                }
                PathRectangle { width: card.width; height: card.height; radius: 24 }
            }
            visible: card.paint.type === "linear"
        }
        Shape {
            anchors.fill: parent
            visible: card.paint.type === "radial"
            ShapePath {
                strokeWidth: 0
                fillGradient: RadialGradient {
                    centerX: card.paint.cx * card.width; centerY: card.paint.cy * card.height
                    focalX: centerX; focalY: centerY
                    centerRadius: Math.min(centerX, card.width - centerX, centerY, card.height - centerY)
                    GradientStop { position: card.paint.stops[0].at; color: card.paint.stops[0].color }
                    GradientStop { position: card.last.at; color: card.last.color }
                }
                PathRectangle { width: card.width; height: card.height; radius: 24 }
            }
        }        GradientHandles {
            id: gh
            anchors.fill: parent
            paint: card.paint; selected: card.selected
            onEdited: p => card.paint = p
            onStopPicked: i => card.selected = i
        }
    }

    Card { id: a; x: 120; y: 200; width: 500; height: 240; paint: win.lin }
    Card { id: b; x: 760; y: 200; width: 240; height: 240; paint: win.rad; selected: 0 }
    Card { id: c; x: 1100; y: 200; width: 440; height: 200; paint: Object.assign({}, win.lin, {angle: -30}); selected: 2 }
}

