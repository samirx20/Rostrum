"""Import and export for Rostrum2D.

Export (every frame through the engine's one render path, then read back; a bad file fails loudly):
    export(eng, "mp4" | "prores4444" | "webm" | "gif" | "png", out, alpha=, depth=, start=, end=,
           quality=, bitrate=)              # quality / bitrate: mp4 only
    write_lottie(scene, path) -> report        the part of the scene Lottie can say; the rest is listed

Import (each source → one import tree → document operations, one undo step):
    import_into(doc, svg_tree(path) | pdf_tree(path) | psd_tree(path) | figma_tree(key, frame, token), into, who)
"""
from .export import export
from .figma import figma_tree
from .lottie import to_lottie, write_lottie
from .pdf import pdf_tree
from .psd import psd_tree
from .svg import svg_tree
from .tree import apply_calls, import_into

__all__ = ["export", "to_lottie", "write_lottie", "svg_tree", "pdf_tree", "psd_tree", "figma_tree", "apply_calls",
           "import_into"]
