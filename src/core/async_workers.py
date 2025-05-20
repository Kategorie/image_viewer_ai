import os
import cv2
import numpy as np
from PIL import Image
from PySide6.QtCore import QThread, Signal

class AsyncUpscaleWorker(QThread):
    finished = Signal(np.ndarray)

    def __init__(self, path, upscaler, cache_path, parent=None):
        super().__init__(parent)
        self.path = path
        self.upscaler = upscaler
        self.cache_path = cache_path

    def run(self):
        try:
            img = cv2.imread(self.path)
            if img is None:
                raise ValueError("이미지를 읽을 수 없습니다.")
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(img)

            if not os.path.exists(self.cache_path):
                output = self.upscaler.upscale(pil_img)
                result_np = np.array(output)
                cv2.imwrite(self.cache_path, cv2.cvtColor(result_np, cv2.COLOR_RGB2BGR))
            else:
                result_np = cv2.imread(self.cache_path)
                result_np = cv2.cvtColor(result_np, cv2.COLOR_BGR2RGB)

            self.finished.emit(result_np)
        except Exception as e:
            print(f"[AsyncUpscaleWorker] 오류: {e}")
            self.finished.emit(None)