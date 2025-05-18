from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QPixmap
from core.upscale_utils import upscale_image

class UpscalingWorker(QThread):
    finished = Signal(QPixmap, str)

    def __init__(self, image_path: str, model_name="real-esrgan"):
        super().__init__()
        self.image_path = image_path
        self.model_name = model_name

    def run(self):
        result_path = upscale_image(self.image_path, self.model_name)
        pixmap = QPixmap(result_path)
        self.finished.emit(pixmap, result_path)