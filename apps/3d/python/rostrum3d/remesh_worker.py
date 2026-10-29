"""remesh.py's worker, run in its own process: `python -I remesh_worker.py <surface.obj> <clean.obj> <faces>`.

Instant Meshes (pyinstantmeshes, BSD-3) rebuilds the surface as about `faces` four-sided faces: its pure-quad mode
splits each face of its own result in four, so it is asked for a quarter of them. Deterministic, so the same surface
gives the same mesh. Exit code 0 and the file written, else a plain last line saying what failed.
"""
import sys


def main(src: str, out: str, faces: str) -> int:
    try:
        import pyinstantmeshes
    except ImportError:
        print("the Instant Meshes package is not installed (pip install pyinstantmeshes)")
        return 2
    pyinstantmeshes.remesh_file(src, out, target_face_count=max(1, int(faces) // 4), pure_quad=True,
                                deterministic=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:4]))
