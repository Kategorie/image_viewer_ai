import logging

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QLabel, QMessageBox

try:
    import imageio.v3 as iio
except ImportError:
    iio = None


class GifPlayer:
    def __init__(self, label: QLabel, scale_factor=1.0, fit_to_window=True):
        self.label = label
        self.scale_factor = scale_factor
        self.fit_to_window = fit_to_window
        self.frames = []
        self.durations = []
        self.index = 0
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)

    def load(self, path):
        if iio is None:
            QMessageBox.warning(None, "라이브러리 누락", "GIF 재생을 위해 imageio가 필요합니다.")
            return False

        self.frames.clear()
        self.durations.clear()
        self.index = 0

        try:
            for frame in iio.imiter(path, plugin="pillow", mode="RGB"):
                self.frames.append(frame)
            meta = iio.immeta(path, plugin="pillow")
            duration = meta.get("duration", 100)
            self.durations = [duration for _ in self.frames]
        except Exception as e:
            logging.error(f"[GIF 오류] {e}")
            return False

        return True

    def start(self):
        if not self.frames:
            return
        self.timer.start(self.durations[0])

    def stop(self):
        self.timer.stop()

    def update_frame(self):
        if not self.frames:
            return

        frame = self.frames[self.index]
        h, w, ch = frame.shape
        bytes_per_line = ch * w
        qimg = QImage(frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg)

        if self.fit_to_window:
            scaled = pixmap.scaled(self.label.size(), Qt.KeepAspectRatio)
        else:
            scaled = pixmap.scaled(pixmap.size() * self.scale_factor, Qt.KeepAspectRatio)

        self.label.setPixmap(scaled)

        self.index = (self.index + 1) % len(self.frames)
        self.timer.start(self.durations[self.index])
