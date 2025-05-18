import os
from PySide6.QtWidgets import QDialog, QVBoxLayout, QScrollArea, QWidget, QHBoxLayout, QLabel, QListWidget
from PySide6.QtCore import Qt

from src.utils.pixmap_cache import QPixmapLRUCache # 캐시 클래스 임포트

class ThumbnailDialog(QDialog):
    def __init__(self, image_dir, parent=None):
        super().__init__(parent)
        self.image_dir = image_dir
        self.setWindowTitle("섬네일 보기")
        self.resize(800, 600)

        layout = QVBoxLayout(self)

        # 캐시 객체 생성
        self.pixmap_cache = QPixmapLRUCache(max_size=100, thumb_size=(100, 100))

        # 상단 섬네일 영역
        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        h_layout = QHBoxLayout(scroll_widget)

        for image_file in os.listdir(image_dir):
            if image_file.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif')):
                full_path = os.path.join(image_dir, image_file)
                thumb = self.pixmap_cache.get(full_path)

                label = QLabel()
                label.setPixmap(thumb)
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                label.mousePressEvent = lambda e, f=image_file: self.open_image(f)
                h_layout.addWidget(label)

        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)

        # 하단 파일 리스트
        list_widget = QListWidget()
        for file in os.listdir(image_dir):
            list_widget.addItem(file)
        list_widget.itemClicked.connect(lambda item: self.open_image(item.text()))
        layout.addWidget(list_widget)

    def open_image(self, filename):
        full_path = os.path.join(self.image_dir, filename)
        self.parent().load_image(full_path)  # 메인 뷰어와 연결된 메서드
        self.close()