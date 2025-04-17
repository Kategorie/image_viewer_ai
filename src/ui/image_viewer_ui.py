import os
import cv2
import zipfile
import tempfile
from PIL import Image, ImageSequence

from PySide6.QtWidgets import (
    QMainWindow, QLabel, QFileDialog, QMenuBar, QDialog, QFormLayout,
    QDialogButtonBox, QLineEdit, QHBoxLayout, QPushButton, QMenu, QMessageBox, QListWidget, QListWidgetItem, QVBoxLayout
)
from PySide6.QtGui import QPixmap, QImage, QAction, QKeyEvent, QWheelEvent, QContextMenuEvent, QActionGroup
from PySide6.QtCore import Qt, QSize, QTimer

from core.config_manager import load_config, save_config, DEFAULT_CONFIG
from core.upscaler import create_upscaler
from core.image_utils import is_image_file, extract_archive

class SettingDialog(QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.setWindowTitle("설정")
        self.config = config
        layout = QFormLayout()

        self.tile_input = QLineEdit(str(config.get("tile", 128)))
        self.scale_input = QLineEdit(str(config.get("scale", 4)))

        self.model_input = QLineEdit(config.get("model_path", ""))
        model_btn = QPushButton("찾아보기")
        model_btn.clicked.connect(self.browse_model_path)
        model_layout = QHBoxLayout()
        model_layout.addWidget(self.model_input)
        model_layout.addWidget(model_btn)

        layout.addRow("Tile:", self.tile_input)
        layout.addRow("Scale:", self.scale_input)
        layout.addRow("Model Path:", model_layout)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)
        self.setLayout(layout)

    def browse_model_path(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "모델 파일 선택", "", "Model Files (*.pth)")
        if file_path:
            self.model_input.setText(file_path)

    def get_values(self):
        return {
            "tile": int(self.tile_input.text()),
            "scale": int(self.scale_input.text()),
            "model_path": self.model_input.text()
        }


class ImageViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Image Viewer")
        self.setGeometry(100, 100, 1000, 700)

        self.config = load_config()
        self.upscaler = create_upscaler(self.config)

        self.image_label = QLabel("이미지를 불러오세요", self)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.setCentralWidget(self.image_label)

        self.image_list = []
        self.current_index = -1
        self.archive_tempdir = None
        self.scale_factor = self.config.get("scale_factor", 1.0)
        self.fit_to_window = self.config.get("fit_to_window", True)
        self.enable_thumbnails = self.config.get("enable_thumbnails", True)

        self.gif_timer = QTimer()
        self.gif_frames = []
        self.gif_delays = []
        self.gif_index = 0

        self.init_menu_bar()

    def init_menu_bar(self):
        menu_bar = QMenuBar(self)
        self.setMenuBar(menu_bar)

        file_menu = menu_bar.addMenu("파일")
        open_action = QAction("이미지/압축 열기", self)
        open_action.triggered.connect(self.open_file_dialog)
        file_menu.addAction(open_action)

        thumbs_action = QAction("썸네일 보기", self, checkable=True)
        thumbs_action.setChecked(self.enable_thumbnails)
        thumbs_action.triggered.connect(self.toggle_thumbnails)
        file_menu.addAction(thumbs_action)

        file_menu.addSeparator()
        file_menu.addAction("종료", self.close)

        settings_menu = menu_bar.addMenu("설정")
        open_setting = QAction("업스케일 설정", self)
        open_setting.triggered.connect(self.open_setting_dialog)
        settings_menu.addAction(open_setting)

        reset_setting = QAction("기본 설정으로 초기화", self)
        reset_setting.triggered.connect(self.reset_settings)
        settings_menu.addAction(reset_setting)
        
        view_menu = menu_bar.addMenu("보기")
        # 보기 크기 그룹 (단일 선택)
        view_mode_group = QActionGroup(self)
        view_mode_group.setExclusive(True)

        fit_action = QAction("화면에 맞춤", self, checkable=True)
        fit_action.setChecked(self.config.get("fit_to_window", True))
        fit_action.triggered.connect(self.toggle_fit_to_window)
        view_mode_group.addAction(fit_action)
        view_menu.addAction(fit_action)

        orig_action = QAction("원본 크기", self, checkable=True)
        orig_action.setChecked(not self.config.get("fit_to_window", True))
        orig_action.triggered.connect(self.toggle_original_size)
        view_mode_group.addAction(orig_action)
        view_menu.addAction(orig_action)

        # 페이지 보기 방식 (단일 선택)
        page_mode_group = QActionGroup(self)
        page_mode_group.setExclusive(True)

        single_action = QAction("한장씩 보기", self, checkable=True)
        single_action.setChecked(self.config.get("page_mode", "single") == "single")
        single_action.triggered.connect(lambda: self.set_page_mode("single"))
        page_mode_group.addAction(single_action)
        view_menu.addAction(single_action)

        double_action = QAction("두장씩 보기", self, checkable=True)
        double_action.setChecked(self.config.get("page_mode", "single") == "double")
        double_action.triggered.connect(lambda: self.set_page_mode("double"))
        page_mode_group.addAction(double_action)
        view_menu.addAction(double_action)

        # 페이지 보기 적용 함수
        def set_page_mode(self, mode):
            self.config["page_mode"] = mode
            save_config(self.config)
            self.refresh_image()

    def toggle_fit_to_window(self, checked):
        self.fit_to_window = checked
        self.config["fit_to_window"] = checked
        save_config(self.config)
        self.refresh_image()

    def toggle_original_size(self, checked):
        self.fit_to_window = not checked
        self.config["fit_to_window"] = not checked
        save_config(self.config)
        self.refresh_image()

    def refresh_image(self):
        if self.current_index >= 0:
            self.open_image(self.image_list[self.current_index])

    def open_file_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "이미지/압축 파일 열기", "", "Images/Archives (*.png *.jpg *.jpeg *.bmp *.gif *.zip *.cbz)"
        )
        if not file_path:
            return

        ext = os.path.splitext(file_path)[1].lower()

        if ext in [".zip", ".cbz"]:
            try:
                self.image_list = extract_archive(file_path)
                if not self.image_list:
                    QMessageBox.information(self, "알림", "이미지가 없습니다.")
                    return
                self.current_index = 0
                self.open_image(self.image_list[0])
            except Exception as e:
                QMessageBox.critical(self, "압축 해제 오류", str(e))
            return

        folder = os.path.dirname(file_path)
        self.image_list = sorted([
            os.path.join(folder, f)
            for f in os.listdir(folder)
            if is_image_file(f)
        ])

        try:
            self.current_index = self.image_list.index(file_path)
        except ValueError:
            QMessageBox.warning(self, "경고", "이미지가 현재 폴더 내에 없습니다.")
            return

        self.open_image(self.image_list[self.current_index])       
            
    def extract_archive(self, archive_path):
        self.archive_tempdir = tempfile.TemporaryDirectory()
        with zipfile.ZipFile(archive_path, 'r') as zipf:
            zipf.extractall(self.archive_tempdir.name)

        self.image_list = sorted([
            os.path.join(self.archive_tempdir.name, f)
            for f in os.listdir(self.archive_tempdir.name)
            if is_image_file(f)
        ])
        self.current_index = 0
        self.open_image(self.image_list[0])

    def open_image(self, path):
        self.gif_timer.stop()
        self.gif_frames.clear()
        self.gif_delays.clear()

        if path.lower().endswith(".gif"):
            pil_img = Image.open(path)
            for frame in ImageSequence.Iterator(pil_img):
                rgba = frame.convert("RGBA")
                delay = frame.info.get("duration", 100)
                self.gif_delays.append(delay)
                data = rgba.tobytes("raw", "RGBA")
                qimg = QImage(data, rgba.width, rgba.height, QImage.Format_RGBA8888)
                self.gif_frames.append(QPixmap.fromImage(qimg))

            self.gif_index = 0
            self.gif_timer.timeout.connect(self.update_gif_frame_pil)
            self.gif_timer.start(self.gif_delays[0])
        else:
            img = cv2.imread(path)
            self.display_image(img)
        self.update_title()

    def update_gif_frame_pil(self):
        if not self.gif_frames:
            return
        pixmap = self.gif_frames[self.gif_index]
        if self.fit_to_window:
            pixmap = pixmap.scaled(self.image_label.size(), Qt.KeepAspectRatio)
        else:
            pixmap = pixmap.scaled(pixmap.size() * self.scale_factor, Qt.KeepAspectRatio)

        self.image_label.setPixmap(pixmap)
        self.gif_index = (self.gif_index + 1) % len(self.gif_frames)
        self.gif_timer.start(self.gif_delays[self.gif_index])

    def display_image(self, img):
        if img is None:
            return
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        bytes_per_line = ch * w
        qt_image = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qt_image)
        if self.fit_to_window:
            pixmap = pixmap.scaled(self.image_label.size(), Qt.KeepAspectRatio)
        else:
            pixmap = pixmap.scaled(pixmap.size() * self.scale_factor, Qt.KeepAspectRatio)
        self.image_label.setPixmap(pixmap)

    def update_title(self):
        if 0 <= self.current_index < len(self.image_list):
            base = os.path.basename(self.image_list[self.current_index])
            folder = os.path.basename(os.path.dirname(self.image_list[self.current_index]))
            total = len(self.image_list)
            self.setWindowTitle(f"{folder} - {base} [{self.current_index+1}/{total}]")

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Right, Qt.Key_Down):
            self.load_next_image()
        elif event.key() in (Qt.Key_Left, Qt.Key_Up):
            self.load_previous_image()
        elif event.key() == Qt.Key_Escape:
            self.close()
        elif event.key() == Qt.Key_Return:
            # 썸네일 보기 옵션과 관계없이 항상 열림
            self.open_thumbnail_dialog(force=True)
    
    def open_thumbnail_dialog(self, force=False):
        if not self.enable_thumbnails and not force:
            return
        if not self.image_list:
            QMessageBox.information(self, "정보", "이미지 리스트가 비어 있습니다.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("썸네일 보기")
        layout = QVBoxLayout(dialog)

        list_widget = QListWidget(dialog)
        list_widget.setIconSize(QSize(160, 160))
        list_widget.setViewMode(QListWidget.IconMode)
        list_widget.setResizeMode(QListWidget.Adjust)
        list_widget.setSpacing(10)

        for idx, path in enumerate(self.image_list):
            item = QListWidgetItem()
            img = cv2.imread(path)
            if img is not None:
                img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                h, w, ch = img.shape
                bytes_per_line = ch * w
                qimg = QImage(img.data, w, h, bytes_per_line, QImage.Format_RGB888)
                pixmap = QPixmap.fromImage(qimg).scaled(160, 160, aspectMode=1)
                item.setIcon(pixmap)
            item.setText(os.path.basename(path))
            list_widget.addItem(item)

        def on_item_clicked(item):
            index = list_widget.row(item)
            if 0 <= index < len(self.image_list):
                self.current_index = index
                self.open_image(self.image_list[self.current_index])
                dialog.accept()

        list_widget.itemClicked.connect(on_item_clicked)
        layout.addWidget(list_widget)
        dialog.setLayout(layout)
        dialog.exec()

    def wheelEvent(self, event: QWheelEvent):
        if event.angleDelta().y() > 0:
            self.load_previous_image()
        else:
            self.load_next_image()

    def contextMenuEvent(self, event: QContextMenuEvent):
        menu = QMenu(self)
        info_action = menu.addAction("이미지 정보 보기")
        action = menu.exec(event.globalPos())
        if action == info_action:
            self.show_image_info()

    def show_image_info(self):
        if 0 <= self.current_index < len(self.image_list):
            path = self.image_list[self.current_index]
            size_kb = os.path.getsize(path) / 1024
            msg = f"파일명: {os.path.basename(path)}\n크기: {size_kb:.2f} KB"
            QMessageBox.information(self, "이미지 정보", msg)

    def load_next_image(self):
        if self.current_index + 1 < len(self.image_list):
            self.current_index += 1
            self.open_image(self.image_list[self.current_index])

    def load_previous_image(self):
        if self.current_index > 0:
            self.current_index -= 1
            self.open_image(self.image_list[self.current_index])

    def toggle_thumbnails(self, checked):
        self.enable_thumbnails = checked
        self.config["enable_thumbnails"] = checked
        save_config(self.config)

    def open_setting_dialog(self):
        dlg = SettingDialog(self.config, self)
        if dlg.exec():
            values = dlg.get_values()
            self.config.update(values)
            save_config(self.config)
            self.upscaler = create_upscaler(self.config)
            QMessageBox.information(self, "설정 적용됨", "업스케일 설정이 변경되었습니다.")

    def reset_settings(self):
        self.config = DEFAULT_CONFIG.copy()
        save_config(self.config)
        self.upscaler = create_upscaler(self.config)
        QMessageBox.information(self, "초기화", "기본 설정으로 초기화되었습니다.")
