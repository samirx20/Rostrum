"""Rostrum2D's operation modules, in registration order (the order agents see them): one list the registry's kind reads
(rostrum_core.modules). A plugin adds its own module to the same list."""
from rostrum_core.modules import ModuleList

OPS = ModuleList("rostrum2d", [
    ".ops_draw", ".ops_expr", ".ops_items", ".ops_keys", ".ops_painting", ".ops_scenes",   # they register on REGISTRY
    ".follow",   # text.follow: a text on a path layer
    ".ops_path", ".ops_stroke",   # vector paths, booleans, stroke width
    ".rig.ops", ".rig.poses", ".rig.guess", ".rig.joints", ".rig.draw", ".rig.mirror",   # bones, IK chains, binds, poses, Bones from part names, joints and posing, the Bone tool, Mirror pose
    ".lipsync.ops",   # lipsync.apply
    ".ops_swap",   # swap.show, blink.add
    ".ops_timing",   # layer.shift, layer.trim: move and trim a layer in time
    ".ops_background",   # background.add, background.move: painted backgrounds
    ".ops_cover",   # background.fit: Cover the frame's move
    ".ops_group", ".ops_mask", ".ops_state", ".ops_align", ".ops_look", ".ops_flip",   # select first, then act
    ".ops_anchor",   # layer.anchor: move the anchor point, keeping the layer in place
    ".ops_clip",   # layer.paste: copy / cut / paste of layers
    ".ops_paint", ".ops_fill", ".paint_transform",   # paint.stroke, paint.fill, stroke.transform: paint, fill and move paint on any element or drawing
    ".ops_frame",   # comp.size, layer.fill_frame
    ".ops_frame_fit",   # frame.fit, frame.cut, frame.home: framing and cuts
    ".ops_depth",   # layer.pin, layer.set_depth: pinned to frame and depth, keeping where it shows
    ".ops_stagger",   # layer.stagger: retiming
    ".ops_path_handles",   # key.path_handles: the path a moving layer travels
    ".ops_anim",   # anim.ease, key.scale, key.paste, key.stagger: rostrum_core.keys.anim_ops; anims.py: anim.list
    ".ops_fill_paint",   # layer.fill, swatch.add / remove / rename: the fill as a paint, project colours
    ".text_styles",   # style.define, style.use, style.detach, style.remove: named text styles
    ".ops_font",   # font.replace: one font for another across the document
    ".ops_counter",   # text.counter: a text whose number counts
])

TOOLS = ModuleList("rostrum2d.mcp", [      # the agent server's tool modules, each with a `tools`; the order is the tools' order
    ".look", ".motion", ".at", ".video", ".draw", ".rig", ".lipsync", ".curves", ".export_tool", ".layout_tool", ".swap_tool",
    ".import_tool", ".diagnose_tool", ".fonts_tool", ".background_tool", ".project_tool", ".soundtrack_tool", ".sound_cue_tool",
    ".brand_tool", ".picture_tool", ".brush_tool", ".painting_tool", ".world",
])
