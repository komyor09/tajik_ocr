"""Align a photo/scan of the ID card to an anonymised template (SIFT keypoints + homography).

The card design (flag, emblem, captions, background guilloche) is identical on every card,
so matching keypoints against a template gives an exact warp regardless of background,
cropping, rotation (including upside down) and perspective. As a bonus it tells which side
of the card is on the picture.
"""

import threading
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from app.passport.card import CARD_H, CARD_W

TEMPLATES = Path(__file__).parent / "templates"
MAX_SIDE = 1400  # query images are downscaled to this for matching
MIN_INLIERS = 25


@dataclass
class Alignment:
    side: str  # "front" | "back"
    card: np.ndarray  # BGR, CARD_W x CARD_H
    inliers: int
    rotated: bool  # card was upside down on the picture


class _Template:
    def __init__(self, side: str, sift: cv2.SIFT):
        img = cv2.imread(str(TEMPLATES / f"{side}.png"), cv2.IMREAD_GRAYSCALE)
        mask = cv2.imread(str(TEMPLATES / f"{side}_mask.png"), cv2.IMREAD_GRAYSCALE)
        self.side = side
        self.kp, self.des = sift.detectAndCompute(img, mask)


_lock = threading.Lock()
_state: dict = {}


def _init():
    with _lock:
        if not _state:
            sift = cv2.SIFT_create(nfeatures=4000)
            _state["sift"] = sift
            _state["templates"] = [_Template("front", sift), _Template("back", sift)]
            _state["matcher"] = cv2.BFMatcher(cv2.NORM_L2)  # exact and deterministic (FLANN is randomised)
    return _state


def _match(t: _Template, kp, des, matcher) -> tuple[np.ndarray | None, int]:
    if des is None or len(des) < 10:
        return None, 0
    pairs = matcher.knnMatch(des, t.des, k=2)
    good = [m for m, n in (p for p in pairs if len(p) == 2) if m.distance < 0.75 * n.distance]
    if len(good) < MIN_INLIERS:
        return None, len(good)
    src = np.float32([kp[m.queryIdx].pt for m in good])
    dst = np.float32([t.kp[m.trainIdx].pt for m in good])
    cv2.setRNGSeed(12345)  # same picture -> same warp
    h, inl = cv2.findHomography(src, dst, cv2.USAC_MAGSAC, 5.0, maxIters=10000, confidence=0.999)
    if h is None:
        return None, 0
    return h, int(inl.sum())


def _sane(h_query_to_card: np.ndarray, query_shape) -> bool:
    """The card outline mapped back onto the photo must be a convex, non-degenerate quad."""
    try:
        inv = np.linalg.inv(h_query_to_card)
    except np.linalg.LinAlgError:
        return False
    corners = np.float32([[0, 0], [CARD_W, 0], [CARD_W, CARD_H], [0, CARD_H]]).reshape(-1, 1, 2)
    quad = cv2.perspectiveTransform(corners, inv).reshape(4, 2)
    if not cv2.isContourConvex(quad.astype(np.float32)):
        return False
    area = cv2.contourArea(quad)
    img_area = query_shape[0] * query_shape[1]
    return 0.05 * img_area < area < 4 * img_area


def align(image_bgr: np.ndarray) -> Alignment | None:
    """Best matching side and the card warped to CARD_W x CARD_H, or None if no card is found."""
    st = _init()
    scale = min(1.0, MAX_SIDE / max(image_bgr.shape[:2]))
    small = (
        cv2.resize(image_bgr, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        if scale < 1
        else image_bgr
    )
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    kp, des = st["sift"].detectAndCompute(gray, None)

    best: tuple[int, str, np.ndarray] | None = None
    for t in st["templates"]:
        h, inliers = _match(t, kp, des, st["matcher"])
        if (
            h is not None
            and inliers >= MIN_INLIERS
            and _sane(h, small.shape)
            and (best is None or inliers > best[0])
        ):
            best = (inliers, t.side, h)
    if best is None:
        return None
    inliers, side, h = best
    # homography is for the downscaled image; fold the scale in and warp the full-resolution original
    s = np.diag([scale, scale, 1.0])
    card = cv2.warpPerspective(
        image_bgr, h @ s, (CARD_W, CARD_H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
    )
    rotated = bool(h[0, 0] < 0 and h[1, 1] < 0)  # template x/y axes flipped relative to the photo
    return Alignment(side=side, card=card, inliers=inliers, rotated=rotated)
