import QtQuick
import RostrumKit

// The view controls in the top bar (SPEC 2d-design-v2 §1.1, never on the frame): "Fit · 57 % ▾". The % is a menu with the same steps as the keys
// (INTERACTION 1.12): Fit (Ctrl+0), 25 – 400 %, 100 % (Ctrl+1), Zoom to selection (F, only with a selection), and the
// Snap switch (INTERACTION 1.11; on by default). The keys live here too: Ctrl+0, Ctrl+1, F / Shift+2 (not while
// typing), Ctrl+= / Ctrl+−. `view` is the canvas's CanvasView; `fitSelection` comes from Stage (it knows the selection).
Item {
    id: vc
    required property var view
    property bool typing: false
    signal fitSelection()
    width: button.width; height: button.height
    readonly property string percent: Math.round(view.zoom * 100) + " %"

    function act(key) {
        if (key === "fit") view.fitAll()
        else if (key === "sel") vc.fitSelection()
        else if (key === "snap") backend.snap.setOn(!backend.snap.on)
        else if (key === "blur") backend.playback.setBlur(!backend.playback.blur)
        else if (key.startsWith("size:")) backend.playback.setSize(key.slice(5))
        else view.show(Number(key) / 100)
    }
    function entries() {
        const out = [{ value: "fit", label: "Fit", keys: "Ctrl 0", group: "a" }]
        for (const p of [25, 50, 100, 200, 400])
            out.push({ value: String(p), label: p + " %", keys: p === 100 ? "Ctrl 1" : "", group: "a" })
        if (backend.selectedLayer !== "") out.push({ value: "sel", label: "Zoom to selection", keys: "F", group: "a" })
        out.push({ value: "snap", label: backend.snap.on ? "Turn snapping off" : "Turn snapping on", group: "b" })
        if (backend.frameInfo.previewSize === true)     // a large composition: how big playing frames are drawn (paused frames and exports are Full)
            for (const o of [["full", "Full"], ["half", "Half"], ["quarter", "Quarter"]])     // one heading, not the label ×3
                out.push({ value: "size:" + o[0], label: o[1], heading: o[0] === "full" ? "Preview while playing" : "",
                           checked: backend.playback.size === o[0], group: "c" })
        if (backend.frameInfo.blur === true)            // motion blur: full blur is slower; off plays one blur step a frame
            out.push({ value: "blur", label: "Motion blur while playing", checked: backend.playback.blur, group: "c" })
        return out
    }

    function openMenu() {                       // under the button, right edges lined up (window px: the kit's menu)
        spot.open(vc.entries())
    }
    MenuSpot { id: spot; anchor: vc; menu: menu; align: "right" }
    Button {
        id: button
        kind: "normal"
        text: (vc.view.fitted ? "Fit · " : "") + vc.percent
        down: menu.opened
        onClicked: vc.openMenu()
    }
    ActionMenu { id: menu; onPicked: (key) => vc.act(key) }

    Shortcut { sequence: "Ctrl+0"; onActivated: vc.view.fitAll() }
    Shortcut { sequence: "Ctrl+1"; onActivated: vc.view.show(1) }
    Shortcut { sequences: ["F", "Shift+2", "@"]; enabled: !vc.typing; onActivated: vc.fitSelection() }
    Shortcut { sequences: ["Ctrl+=", "Ctrl++", StandardKey.ZoomIn]; onActivated: vc.view.step(1) }
    Shortcut { sequences: ["Ctrl+-", StandardKey.ZoomOut]; onActivated: vc.view.step(-1) }
}
