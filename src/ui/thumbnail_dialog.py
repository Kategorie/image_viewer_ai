import os
from PySide6.QtWidgets import QDialog, QVBoxLayout, QScrollArea, QWidget, QHBoxLayout, QLabel, QListWidget
from PySide6.QtCore import Qt, Signal

from utils.pixmap_cache import QPixmapLRUCache # 캐시 클래스 임포트

class ThumbnailDialog(QDialog):
    imageSelected = Signal(str)
    
    def __init__(self, image_dir, parent=None):
        super().__init__(parent)
        self.image_dir = image_dir  # 현재 이미지가 있는 폴더 경로
        self.setWindowTitle("섬네일 보기")
        self.resize(800, 600)

        layout = QVBoxLayout(self)

        self.pixmap_cache = QPixmapLRUCache(max_size=100, thumb_size=(100, 100))

        # 섬네일 영역
        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        h_layout = QHBoxLayout(scroll_widget)

        # self.image_dir 기준으로 파일 목록 가져오기
        for image_file in sorted(os.listdir(self.image_dir)):
            if image_file.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif')):
                full_path = os.path.join(self.image_dir, image_file)
                thumb = self.pixmap_cache.get(full_path)

                label = QLabel()
                label.setPixmap(thumb)
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                label.mousePressEvent = lambda e, f=image_file: self.open_image(f)
                h_layout.addWidget(label)

        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)

        self.list_widget.itemClicked.connect(self.on_item_clicked)

        # 파일 리스트
        list_widget = QListWidget()
        for file in sorted(os.listdir(self.image_dir)):
            list_widget.addItem(file)
        list_widget.itemClicked.connect(lambda item: self.open_image(item.text()))
        layout.addWidget(list_widget)

        self.imageSelected.connect(self.parent().load_image)  # 연결만 함

    def open_image(self, filename):
        full_path = os.path.join(self.image_dir, filename)
        self.imageSelected.emit(full_path)
        self.close()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # 현재 썸네일 중 가장 큰 이미지 기준으로 높이 자동 조정
        max_height = 0
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item and item.icon().availableSizes():
                max_height = max(max_height, item.icon().availableSizes()[0].height())
        self.list_widget.setFixedHeight(max(180, max_height + 40))
    
    def on_item_clicked(self, item):
        path = item.data(Qt.UserRole)
        self.imageSelected.emit(path)