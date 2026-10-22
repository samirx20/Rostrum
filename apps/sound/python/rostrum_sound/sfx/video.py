"""Reading video for the eyes tools: open, fetch a frame, labelled tiles (OpenCV, loaded on demand: opencv.py)."""
import os


def cv2():
    from .opencv import cv2 as load      # only when a video is read: `python -m rostrum_sound.sfx.opencv` stays clean
    return load()


def open_video(path):
    """-> (capture, fps, frame count). Fails loudly on a missing or unreadable video."""
    path = os.fspath(path)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"{path}: video file not found")
    cv = cv2()
    cap = cv.VideoCapture(path)
    if not cap.isOpened():
        raise ValueError(f"{path}: cannot open video")
    fps, n = cap.get(cv.CAP_PROP_FPS), int(cap.get(cv.CAP_PROP_FRAME_COUNT))
    if not fps or n <= 0:
        cap.release()
        raise ValueError(f"{path}: video has no frame rate or frame count")
    return cap, fps, n


def read_frame(cap, idx, path="video"):
    cap.set(cv2().CAP_PROP_POS_FRAMES, idx)
    ok, fr = cap.read()
    if not ok:
        raise ValueError(f"{path}: cannot read frame {idx}")
    return fr


def tile(fr, text, width):
    """Frame scaled to `width`, with a black label bar on top."""
    h = int(fr.shape[0] * width / fr.shape[1])
    cv = cv2()
    img = cv.resize(fr, (width, h), interpolation=cv.INTER_AREA)
    cv.rectangle(img, (0, 0), (width, 18), (0, 0, 0), -1)
    cv.putText(img, text, (4, 13), cv.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv.LINE_AA)
    return img


def write_png(path, img):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    if not cv2().imwrite(os.fspath(path), img):
        raise ValueError(f"{path}: could not write picture")
    return str(path)
