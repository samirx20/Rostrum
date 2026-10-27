import QtQuick
import RostrumKit

// How the viewport shows the scene, in one top-bar button (header SPEC §3 "Rostrum3D"), built like 2D's "Fit · 53 % ▾":
// "Shot camera · Quick ▾" ("Shot · Quick" in a window narrower than 1400 px). Its menu: Camera (the shot camera, a free
// camera, through the selected light while one is selected; the one in use ticked), then Look
// (Quick, the live view; Final, the render's own picture in place; Shift+F flips it). The choices are read as it opens.
// openMenu() is the scripted `view` step (Main.qml openView).
Item {
    id: vl
    width: button.width; height: button.height
    readonly property bool narrow: (vl.Window.window ? vl.Window.window.width : 1646) < 1400
    readonly property var cameras: narrow ? ({ shot: "Shot", free: "Free", light: "Light" })
                                          : ({ shot: "Shot camera", free: "Free camera", light: "Through the light" })
    readonly property string lookWord: viewport.look === "final" ? "Final" : "Quick"

    function keyOf(job) { return vl.Window.window && vl.Window.window.keyFor ? vl.Window.window.keyFor(job) : "" }
    function entries() {
        const m = viewport.mode
        // no key chip on the cameras: ` (shot / free) is on the Keys sheet; a lone ` in a chip reads as a speck
        const out = [{ value: "cam:shot", label: "Shot camera", checked: m === "shot", heading: "Camera" },
                     { value: "cam:free", label: "Free camera", checked: m === "free" }]
        if (viewport.canThroughLight)       // follows the selection
            out.push({ value: "cam:light", label: "Through the selected light", checked: m === "light" })
        const fin = viewport.look === "final"
        out.push({ value: "look:quick", label: "Quick", checked: !fin, heading: "Look", group: "look", keys: fin ? keyOf("look") : "" })
        out.push({ value: "look:final", label: "Final", checked: fin, group: "look", keys: fin ? "" : keyOf("look") })
        return out
    }
    function openMenu() { spot.open(vl.entries()) }
    function act(v) {
        if (v.startsWith("cam:")) viewport.setMode(v.slice(4))
        else if (v.startsWith("look:")) viewport.setLook(v.slice(5))
    }

    MenuSpot { id: spot; anchor: vl; menu: menu; align: "right" }
    Button {
        id: button
        objectName: "viewLook"
        kind: "normal"; chevron: true
        text: (vl.cameras[viewport.mode] || vl.cameras.shot) + " · " + vl.lookWord
        tip: "Camera and look"
        // its room is kept for the usual words (the shot or free camera, Quick or Final), so flipping them never moves
        // the bar beside it; only "Through the light" is wider
        width: Math.max(implicitWidth, room.implicitWidth)
        down: menu.opened
        Button { id: room; visible: false; kind: "normal"; chevron: true; text: (vl.narrow ? "Free" : "Free camera") + " · Quick" }
        onClicked: vl.openMenu()
    }
    ActionMenu { id: menu; onPicked: (v) => vl.act(v) }
}
