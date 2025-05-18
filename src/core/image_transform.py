import cv2
import numpy as np
from PySide6.QtCore import Qt, QSize

def apply_rotation(img: np.ndarray, angle: int) -> np.ndarray:
    if angle == 0:
        return img
    rot_map = {
        90: cv2.ROTATE_90_CLOCKWISE,
        180: cv2.ROTATE_180,
        270: cv2.ROTATE_90_COUNTERCLOCKWISE
    }
    return cv2.rotate(img, rot_map.get(angle, 0))

def apply_flip(img: np.ndarray, horizontal: bool = False, vertical: bool = False) -> np.ndarray:
    if horizontal:
        img = cv2.flip(img, 1)
    if vertical:
        img = cv2.flip(img, 0)
    return img

def apply_scaling(pixmap, scale_factor, target_size=None):
    if target_size:
        width = int(target_size.width() * scale_factor)
        height = int(target_size.height() * scale_factor)
        return pixmap.scaled(QSize(width, height), Qt.KeepAspectRatio, Qt.SmoothTransformation)
    else:
        width = int(pixmap.width() * scale_factor)
        height = int(pixmap.height() * scale_factor)
        return pixmap.scaled(width, height, Qt.KeepAspectRatio, Qt.SmoothTransformation)