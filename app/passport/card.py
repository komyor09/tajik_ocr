"""Find the ID card on a photo and warp it to a canonical 1024x640 image."""

import cv2
import numpy as np

CARD_W, CARD_H = 1024, 640  # ID-1 format 85.6 x 54 mm, aspect ~1.586


def _order(pts: np.ndarray) -> np.ndarray:
    """Corners as top-left, top-right, bottom-right, bottom-left."""
    s, d = pts.sum(axis=1), np.diff(pts, axis=1).ravel()
    return np.array([pts[s.argmin()], pts[d.argmin()], pts[s.argmax()], pts[d.argmax()]], dtype=np.float32)


def find_card(image_bgr: np.ndarray) -> np.ndarray | None:
    """Corner points of the card, or None when the image already is the card (a scan)."""
    h, w = image_bgr.shape[:2]
    scale = 800 / max(h, w)
    small = cv2.resize(image_bgr, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    gray = cv2.GaussianBlur(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY), (5, 5), 0)
    edges = cv2.dilate(cv2.Canny(gray, 30, 90), np.ones((3, 3), np.uint8))
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    img_area = small.shape[0] * small.shape[1]
    for c in sorted(contours, key=cv2.contourArea, reverse=True)[:5]:
        area = cv2.contourArea(c)
        if area < 0.15 * img_area:
            break
        if area > 0.95 * img_area:  # contour is the image border: a tight scan
            continue
        quad = cv2.approxPolyDP(c, 0.02 * cv2.arcLength(c, True), True)
        if len(quad) != 4:
            rect = cv2.minAreaRect(c)  # rounded corners -> fall back to min-area box
            if area / max(rect[1][0] * rect[1][1], 1) < 0.9:
                continue
            quad = cv2.boxPoints(rect)
        pts = _order(quad.reshape(4, 2).astype(np.float32) / scale)
        width = np.linalg.norm(pts[1] - pts[0]) + np.linalg.norm(pts[2] - pts[3])
        height = np.linalg.norm(pts[3] - pts[0]) + np.linalg.norm(pts[2] - pts[1])
        ratio = max(width, height) / max(min(width, height), 1)
        if 1.35 < ratio < 1.85:
            return pts
    return None


def normalize(image_bgr: np.ndarray) -> tuple[np.ndarray, bool]:
    """Warp the card to CARD_W x CARD_H, landscape. Returns (card, found_on_photo)."""
    pts = find_card(image_bgr)
    if pts is None:
        card = image_bgr
        if card.shape[0] > card.shape[1]:
            card = cv2.rotate(card, cv2.ROTATE_90_CLOCKWISE)
        return cv2.resize(card, (CARD_W, CARD_H), interpolation=cv2.INTER_CUBIC), False

    tl, tr, br, bl = pts
    if np.linalg.norm(tr - tl) < np.linalg.norm(bl - tl):  # card is portrait on the photo
        pts = np.array([bl, tl, tr, br], dtype=np.float32)
    dst = np.array([[0, 0], [CARD_W - 1, 0], [CARD_W - 1, CARD_H - 1], [0, CARD_H - 1]], dtype=np.float32)
    m = cv2.getPerspectiveTransform(pts, dst)
    return cv2.warpPerspective(image_bgr, m, (CARD_W, CARD_H), flags=cv2.INTER_CUBIC), True


def rotate180(card: np.ndarray) -> np.ndarray:
    return cv2.rotate(card, cv2.ROTATE_180)
