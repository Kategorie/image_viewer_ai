import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QListWidget, QListWidgetItem, QStyledItemDelegate
)
from PySide6.QtCore import Qt, Signal, QSize, QRect
from PySide6.QtGui import QIcon
from utils.pixmap_cache import QPixmapLRUCache

class ThumbnailDialog(QDialog):
    imageSelected = Signal(str)

    def __init__(self, image_dir, parent=None):
        super().__init__(parent)
        self.image_dir = image_dir
        self.setWindowTitle("썸네일 보기")
        self.resize(800, 400)

        self.pixmap_cache = QPixmapLRUCache(max_size=100, thumb_size=(150, 150))

        layout = QVBoxLayout(self)

        # ✅ 썸네일 리스트 (가로 스크롤)
        self.thumbnail_list_widget = QListWidget()
        self.thumbnail_list_widget.setViewMode(QListWidget.IconMode)
        self.thumbnail_list_widget.setMovement(QListWidget.Static)
        self.thumbnail_list_widget.setResizeMode(QListWidget.Adjust)
        self.thumbnail_list_widget.setFlow(QListWidget.LeftToRight)
        self.thumbnail_list_widget.setWrapping(False)
        self.thumbnail_list_widget.setSpacing(10)
        self.thumbnail_list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.thumbnail_list_widget.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.thumbnail_list_widget.setFixedHeight(180)

        thumb_size = QSize(150, 150)
        self.thumbnail_list_widget.setIconSize(thumb_size)
        self.thumbnail_list_widget.setItemDelegate(CenteredIconDelegate(thumb_size))

        # ✅ 파일명 리스트 (세로 리스트)
        self.filename_list_widget = QListWidget()
        self.filename_list_widget.setSelectionMode(QListWidget.SingleSelection)
        self.filename_list_widget.setViewMode(QListWidget.ListMode)

        # 🔄 이미지 로드 및 리스트 구성
        for image_file in sorted(os.listdir(self.image_dir)):
            if image_file.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif')):
                full_path = os.path.join(self.image_dir, image_file)

                # 썸네일 항목
                thumb = self.pixmap_cache.get(full_path)
                thumb_item = QListWidgetItem(QIcon(thumb), "")
                thumb_item.setData(Qt.UserRole, full_path)
                thumb_item.setSizeHint(QSize(160, 160))
                self.thumbnail_list_widget.addItem(thumb_item)

                # 파일명 항목
                file_item = QListWidgetItem(image_file)
                file_item.setData(Qt.UserRole, full_path)
                self.filename_list_widget.addItem(file_item)

        # 🔗 이벤트 연결
        self.thumbnail_list_widget.itemDoubleClicked.connect(self.emit_and_close)
        self.filename_list_widget.itemClicked.connect(self.sync_thumbnail_selection)
        self.filename_list_widget.itemDoubleClicked.connect(self.emit_and_close)

        layout.addWidget(self.thumbnail_list_widget)
        layout.addWidget(self.filename_list_widget)

        self.imageSelected.connect(self.parent().load_image)

    def closeEvent(self, event):
        self.pixmap_cache.cache.clear()
        super().closeEvent(event)

    def sync_thumbnail_selection(self, item):
        """텍스트 리스트 클릭 시 썸네일 리스트에서 동일 항목을 선택만 한다 (emit 없음)."""
        target_path = item.data(Qt.UserRole)
        for i in range(self.thumbnail_list_widget.count()):
            thumb_item = self.thumbnail_list_widget.item(i)
            if thumb_item.data(Qt.UserRole) == target_path:
                self.thumbnail_list_widget.setCurrentRow(i)
                self.thumbnail_list_widget.scrollToItem(thumb_item, QListWidget.PositionAtCenter)
                break

    def emit_and_close(self, item):
        """더블 클릭 시 이미지 로드 및 창 닫기"""
        path = item.data(Qt.UserRole)
        self.imageSelected.emit(path)
        self.close()

class CenteredIconDelegate(QStyledItemDelegate):
    def __init__(self, icon_size, parent=None):
        super().__init__(parent)
        self.icon_size = icon_size

    def paint(self, painter, option, index):
        icon = index.data(Qt.DecorationRole)
        if icon:
            rect = option.rect
            icon_size = self.icon_size
            x = rect.x() + (rect.width() - icon_size.width()) // 2
            y = rect.y() + (rect.height() - icon_size.height()) // 2
            icon.paint(painter, QRect(x, y, icon_size.width(), icon_size.height()), Qt.AlignCenter)

    def sizeHint(self, option, index):
        return QSize(self.icon_size.width() + 20, self.icon_size.height() + 20)