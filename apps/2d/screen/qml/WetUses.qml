import QtQuick

// Wet ink on every layer using a painting (screen2d/wet_uses.py), in world px: the stroke being painted in place is
// stamped once in the painting's own px (painter.wet, `uses`), drawn once into one texture covering the painting (and
// the brush's reach past its edges), and that texture is laid on each use through its place and its painted fill's
// mapping, clipped to the use's box; on Tile once per tile, a seamless painting's wrapped copies inside it. A pen move
// changes the two ink pictures only: the copies never change during a stroke, so 50 uses cost what one does.
Item {
    id: wu
    property real zoom: 1
    readonly property var w: painter.wet
    readonly property var first: w.uses.length > 0 ? w.uses[0] : null
    readonly property real pad: first ? first.pad : 0
    readonly property real pw: first ? first.pw : 1
    readonly property real ph: first ? first.ph : 1
    readonly property int most: 2048                       // the texture's largest side (a bigger painting: drawn smaller)
    function m(a, z) { return Qt.matrix4x4(z * a[0], z * a[2], 0, z * a[4], z * a[1], z * a[3], 0, z * a[5], 0, 0, 1, 0, 0, 0, 0, 1) }

    Item {          // the ink in the painting's px, from (-pad, -pad): only ever drawn into `ink`
        id: inkItem
        visible: wu.first !== null
        width: wu.pw + 2 * wu.pad; height: wu.ph + 2 * wu.pad
        Image { visible: wu.w.drySerial > 0
                x: (wu.w.dryBox.x || 0) + wu.pad; y: (wu.w.dryBox.y || 0) + wu.pad
                width: wu.w.dryBox.w || 0; height: wu.w.dryBox.h || 0
                source: wu.w.drySerial > 0 && wu.first ? "image://wet/dry-" + wu.w.drySerial : ""; cache: false; asynchronous: false }
        Image { visible: wu.w.serial > 0
                x: (wu.w.box.x || 0) + wu.pad; y: (wu.w.box.y || 0) + wu.pad
                width: wu.w.box.w || 0; height: wu.w.box.h || 0
                source: wu.w.serial > 0 && wu.first ? "image://wet/tip-" + wu.w.serial : ""; cache: false; asynchronous: false }
    }
    ShaderEffectSource {
        id: ink
        sourceItem: wu.first ? inkItem : null; hideSource: true; live: true; smooth: true
        readonly property real k: Math.min(1, wu.most / Math.max(inkItem.width, inkItem.height))
        textureSize: Qt.size(Math.ceil(inkItem.width * k), Math.ceil(inkItem.height * k))
        width: 0; height: 0
    }
    Repeater {
        model: wu.w.uses
        delegate: Item {            // the use's own px (its place), its box clipping
            id: use
            required property var modelData
            width: modelData.w; height: modelData.h; clip: true
            transform: Matrix4x4 { matrix: wu.m(use.modelData.own, wu.zoom) }
            Item {                  // the painting's px in it
                transform: Matrix4x4 { matrix: wu.m(use.modelData.inner, 1) }
                Item {
                    width: use.modelData.pw; height: use.modelData.ph; clip: use.modelData.clip
                    Repeater {
                        model: use.modelData.offsets
                        delegate: ShaderEffect {
                            required property var modelData
                            x: modelData[0] - wu.pad; y: modelData[1] - wu.pad
                            width: inkItem.width; height: inkItem.height
                            property variant source: ink
                        }
                    }
                }
            }
        }
    }
}
