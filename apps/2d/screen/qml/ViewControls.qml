import QtQuick
import RostrumKit

// The view controls in the top bar (SPEC 2d-design-v2 §1.1, never on the frame): "Fit · 57 % ▾". The % is a menu with the same steps as the keys
// (INTERACTION 1.12): Fit the frame (Ctrl+0), Fit everything (Shift+1), 25 – 400 %, 100 % (Ctrl+1), Zoom to selection
// (F, only with a selection), Look through the frame (Shift+C, a check mark: LookThrough.qml), the Snap switch (INTERACTION 1.11; on by default) and "Show the frame's path" (on at first).
// The keys live here too: Ctrl+0, Ctrl+1, F / Shift+2 and Shift+C (not while typing), Ctrl+= / Ctrl+−. `view` is the canvas's CanvasView; `fitSelection` comes from Stage (it knows the selection).
Item {
    id: vc
    required property var view
    property var look: null              // Stage's LookThrough
    property bool typing: false
    signal fitSelection()
    width: button.width; height: button.height
    readonly property string percent: Math.round(view.zoom * 100) + " %"

    function fitFrame() { view.fitAll(backend.frameView.fitRect()) }
    function fitEverything() { view.fitEverything(backend.frameView.everythingRect()) }
    function act(key) {
        if (key === "fit") vc.fitFrame()
        else if (key === "everything") vc.fitEverything()
        else if (key === "sel") vc.fitSelection()
        else if (key === "look") vc.look.toggle()
        else if (key === "in") vc.view.step(1)
        else if (key === "out") vc.view.step(-1)
        else if (key === "snap") backend.snap.setOn(!backend.snap.on)
        else if (key === "framepath") backend.motionPath.setFramePath(!backend.motionPath.framePath)
        else if (key === "blur") backend.playback.setBlur(!backend.playback.blur)
        else if (key.startsWith("size:")) backend.playback.setSize(key.slice(5))
        else view.show(Number(key) / 100)
    }
    function entries() {
        const out = backend.viewEntries()                   // the steps Ctrl+K lists too (view_commands.py)
        for (const e of out) if (e.value === "look") e.checked = vc.look.on
        out.push({ value: "snap", label: backend.snap.on ? "Turn snapping off" : "Turn snapping on", group: "b" })
        out.push({ value: "framepath", label: "Show the frame's path",            // faint while something else is picked
                   checked: backend.motionPath.framePath, group: "b" })
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
    Connections { target: backend; function onViewRequested(key) { vc.act(key) } }       // Ctrl+K's view commands
    MenuSpot { id: spot; anchor: vc; menu: menu; align: "right" }
    Button {
        id: button
        kind: "normal"
        text: (vc.view.fitted ? "Fit · " : "") + vc.percent
        down: menu.opened
        onClicked: vc.openMenu()
    }
    ActionMenu { id: menu; onPicked: (key) => vc.act(key) }

    // The keys of the key map (Ctrl+0, Ctrl+1, F, Shift+C, Ctrl+= / Ctrl+-) come through the one KeyMap (Main.qml windowJobs → key(job));
    // only the extra spellings of two of them live here
    function key(job) {
        if (job === "fit_all") fitFrame()
        else if (job === "actual_size") view.show(1)
        else if (job === "fit") fitSelection()
        else if (job === "look_through") look.toggle()
        else if (job === "zoom_in") view.step(1)
        else if (job === "zoom_out") view.step(-1)
    }
    Shortcut { sequences: ["Shift+1", "!"]; enabled: !vc.typing && !OpenPopups.takes(["Shift+1"]); onActivated: vc.fitEverything() }
    Shortcut { sequences: ["Shift+2", "@"]; enabled: !vc.typing && !OpenPopups.takes(["Shift+2"]); onActivated: vc.fitSelection() }
}
