"""Reading video for the eyes tools: open, fetch a frame, labelled tiles."""
import os

import cv2


def open_video(path):
    """-> (capture, fps, frame count). Fails loudly on a missing or unreadable video."""
    path = os.fspath(path)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"{path}: video file not found")
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise ValueError(f"{path}: cannot open video")
    fps, n = cap.get(cv2.CAP_PROP_FPS), int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if not fps or n <= 0:
        cap.release()
        raise ValueError(f"{path}: video has no frame rate or frame count")
    return cap, fps, n


def read_frame(cap, idx, path="video"):
    cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
    ok, fr = cap.read()
    if not ok:
        raise ValueError(f"{path}: cannot read frame {idx}")
    return fr


def tile(fr, text, width):
    """Frame scaled to `width`, with a black label bar on top."""
    h = int(fr.shape[0] * width / fr.shape[1])
    img = cv2.resize(fr, (width, h), interpolation=cv2.INTER_AREA)
    cv2.rectangle(img, (0, 0), (width, 18), (0, 0, 0), -1)
    cv2.putText(img, text, (4, 13), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
    return img


def write_png(path, img):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    if not cv2.imwrite(os.fspath(path), img):
        raise ValueError(f"{path}: could not write picture")
    return str(path)
