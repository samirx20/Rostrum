"""`python -m rostrum2d.mcp`: the 2D agent surface, markup films (rostrum2d.markup.mcp; decided by the tool experiment
of 2026-10-30). ROSTRUM2D_TOOLSET=classic starts the older 28-tool document server instead, kept installable for
comparison only (ROSTRUM2D_TOOLSET=small: its four-tool form)."""
import os


def run():
    if os.environ.get("ROSTRUM2D_TOOLSET", "") in ("classic", "full", "small"):
        from .server import main
    else:
        from ..markup.mcp import main
    main()


if __name__ == "__main__":
    run()
