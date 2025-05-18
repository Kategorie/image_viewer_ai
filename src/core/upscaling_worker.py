# QPixmapLRUCache는 캐시를 관리하는 클래스입니다.

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QPixmap

# 실제 업스케일 함수는 아래에서 임포트하거나 정의하세요
from core.upscaler import upscale_image  # 예: real_esrgan_upscale

class UpscalingWorker(QThread):
    finished = Signal(QPixmap, str)  # 결과와 원본 파일 경로를 반환

    def __init__(self, image_path: str):
        super().__init__()
        self.image_path = image_path

    def run(self):
        # 여기서 실제 AI 모델을 호출
        result_path = upscale_image(self.image_path)
        pixmap = QPixmap(result_path)
        self.finished.emit(pixmap, result_path)