from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt
from collections import OrderedDict

class QPixmapLRUCache:
    def __init__(self, max_size=100, thumb_size=(100, 100)):
        self.max_size = max_size
        self.thumb_size = thumb_size
        self.cache = OrderedDict()

    def get(self, image_path: str) -> QPixmap:
        if image_path in self.cache:
            # 최근 사용으로 갱신
            self.cache.move_to_end(image_path)
            return self.cache[image_path]

        # 새 QPixmap 생성 및 크기 조정
        pixmap = QPixmap(image_path).scaled(
            self.thumb_size[0],
            self.thumb_size[1],
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

        # 캐시 삽입
        self.cache[image_path] = pixmap

        # 캐시 초과 시 제거
        if len(self.cache) > self.max_size:
            self.cache.popitem(last=False)  # 가장 오래된 항목 제거

        return pixmap
    
    def clear(self):
        self.cache.clear()