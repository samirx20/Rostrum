"""Import and export for Rostrum2D.

Export (every frame through the engine's one render path, then read back; a bad file fails loudly):
    export(eng, "mp4" | "prores4444" | "webm" | "gif" | "png", out, alpha=, depth=, start=, end=,
           quality=, bitrate=)              # quality / bitrate: mp4 only
    write_lottie(scene, path) -> report        the part of the scene Lottie can say; the rest is listed

Import (each source → one import tree → document operations, one undo step):
    import_into(doc, svg_tree(path) | pdf_tree(path) | psd_tree(path) | figma_tree(key, frame, token), into, who)

Each name loads its module on first use (PEP 562): the screen reads `rostrum2d.io.formats` at start, and the PDF and
PSD readers (pypdf, pypdfium2, psd_tools) cost most of a second to import, so they load when a file of theirs is read.
"""
from importlib import import_module

_FROM = {"export": "export", "to_lottie": "lottie", "write_lottie": "lottie", "svg_tree": "svg", "pdf_tree": "pdf",
         "psd_tree": "psd", "figma_tree": "figma", "apply_calls": "tree", "import_into": "tree"}
__all__ = list(_FROM)


def __getattr__(name):
    if name not in _FROM:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return getattr(import_module(f".{_FROM[name]}", __name__), name)
