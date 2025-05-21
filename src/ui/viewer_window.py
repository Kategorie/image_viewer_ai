import os
import cv2
import hashlib
import numpy as np
from PIL import Image
import logging
import time


try:
    import imageio.v3 as iio
except ImportError:
    iio = None

# 로깅 설정 추가
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)

from PySide6.QtWidgets import (
    QMainWindow, QLabel, QFileDialog, QMenuBar, QMenu, QMessageBox
)
from PySide6.QtGui import QPixmap, QImage, QWheelEvent, QContextMenuEvent, QAction, QActionGroup
from PySide6.QtCore import Qt, QTimer

from config.settings_loader import AppSettings
from plugins.plugin_loader import create_upscaler
from utils.image_utils import is_image_file, extract_archive, get_file_extension
from ui.setting_dialog import SettingDialog
from ui.thumbnail_dialog import ThumbnailDialog
from utils.gif_player import GifPlayer
from core.image_transform import apply_rotation, apply_flip, apply_scaling
from core.async_workers import AsyncUpscaleWorker

class ImageViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Image Viewer")
        self.setGeometry(100, 100, 1000, 700)

        self.settings = AppSettings.load_from_json("config/settings.json")
        self.settings.set_on_change_callback(self.refresh_image)
        self.upscale_worker = None

        self.upscaler = create_upscaler("real-esrgan", self.settings)

        self.image_label = QLabel("이미지를 불러오세요", self)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.setCentralWidget(self.image_label)

        self.rotation_angle = 0
        self.flip_horizontal = False
        self.flip_vertical = False
        self.enabled_upscale = self.settings.enabled_upscale
        self.current_image_path = None
        self.current_image_dir = None
        self.anim_timer = QTimer(self)

        self.image_list = []
        self.current_index = -1
        self.archive_tempdir = None
        self.scale_factor = self.settings.scale_factor
        self.fit_to_window = self.settings.fit_to_window
        self.enabled_thumbnails = self.settings.enabled_thumbnails
        
        # gif 플레이어 초기화
        self.gif_player = GifPlayer(self.image_label, self.scale_factor, self.fit_to_window)

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
        thumbs_action.setChecked(self.enabled_thumbnails)
        thumbs_action.triggered.connect(self.toggle_thumbnails)
        file_menu.addAction(thumbs_action)

        file_menu.addSeparator()
        file_menu.addAction("종료", self.close)

        settings_menu = menu_bar.addMenu("설정")
        setting_dialog_action = QAction("환경설정", self)
        setting_dialog_action.triggered.connect(self.open_setting_dialog)
        settings_menu.addAction(setting_dialog_action)

        self.upscale_action  = QAction("AI 업스케일", self)
        self.upscale_action.triggered.connect(lambda: self.start_upscaling(self.current_image_path))
        settings_menu.addAction(self.upscale_action)

        view_menu = menu_bar.addMenu("보기")
        view_mode_group = QActionGroup(self)
        view_mode_group.setExclusive(True)

        fit_action = QAction("화면에 맞춤", self, checkable=True)
        fit_action.setChecked(self.fit_to_window)
        fit_action.triggered.connect(self.toggle_fit_to_window)
        view_mode_group.addAction(fit_action)
        view_menu.addAction(fit_action)

        orig_action = QAction("원본 크기", self, checkable=True)
        orig_action.setChecked(not self.fit_to_window)
        orig_action.triggered.connect(self.toggle_original_size)
        view_mode_group.addAction(orig_action)
        view_menu.addAction(orig_action)

        view_menu.addSeparator()
        page_mode_group = QActionGroup(self)
        page_mode_group.setExclusive(True)

        single_page_action = QAction("한 장 보기", self, checkable=True)
        single_page_action.setChecked(self.settings.page_mode == "single")
        single_page_action.triggered.connect(lambda: self.set_page_mode("single"))
        page_mode_group.addAction(single_page_action)
        view_menu.addAction(single_page_action)

        double_page_action = QAction("두 장 보기", self, checkable=True)
        double_page_action.setChecked(self.settings.page_mode == "double")
        double_page_action.triggered.connect(lambda: self.set_page_mode("double"))
        page_mode_group.addAction(double_page_action)
        view_menu.addAction(double_page_action)

    def toggle_thumbnails(self, checked):
        self.enabled_thumbnails = checked
        self.settings.enabled_thumbnails = checked
        self.settings.save_to_json("config/settings.json")

    def toggle_upscale(self):
        self.enabled_upscale = not self.enabled_upscale
        self.settings.enabled_upscale = self.enabled_upscale
        self.settings.save_to_json("config/settings.json")

    def toggle_fit_to_window(self, checked):
        self.fit_to_window = checked
        self.settings.fit_to_window = checked
        self.settings.save_to_json("config/settings.json")
        self.refresh_image()

    def toggle_original_size(self, checked):
        self.toggle_fit_to_window(not checked)

    def refresh_image(self):
        if self.current_index >= 0 and self.current_index < len(self.image_list):
            self.open_image(self.image_list[self.current_index])

    def open_file_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "파일 열기", "", "Images (*.png *.jpg *.jpeg *.bmp *.gif *.zip *.cbz)")
        if file_path:
            self.open_image(file_path)

    def open_setting_dialog(self):
        dialog = SettingDialog(self.settings, self)
        if dialog.exec():
            self.settings = dialog.modified
            self.settings.save_to_json("config/settings.json")
            self.upscaler = create_upscaler("real-esrgan", self.settings)
            self.scale_factor = self.settings.scale_factor
            self.fit_to_window = self.settings.fit_to_window
            self.enabled_thumbnails = self.settings.enabled_thumbnails
            self.enabled_upscale = self.settings.enabled_upscale
            self.refresh_image()

    def set_page_mode(self, mode):
        self.settings.page_mode = mode
        self.settings.save_to_json("config/settings.json")
        self.refresh_image()

    def get_cached_path(self, image_path: str) -> str:
        import os
        import hashlib

        cache_dir = os.path.join(os.path.dirname(__file__), "../cache")
        os.makedirs(cache_dir, exist_ok=True)
        name_hash = hashlib.md5(image_path.encode()).hexdigest()
        ext = os.path.splitext(image_path)[1].lower()
        cache_name = f"{name_hash}{ext}"
        return os.path.join(cache_dir, cache_name)

    def open_image(self, path):
        folder = os.path.dirname(path)
        self.image_list = sorted([
            os.path.join(folder, f) for f in os.listdir(folder)
            if f.lower().endswith((".jpg", ".jpeg", ".png", ".bmp", ".gif"))
        ])
        path = os.path.abspath(path)

        if path in map(os.path.abspath, self.image_list):
            self.current_index = list(map(os.path.abspath, self.image_list)).index(path)
        else:
            self.image_list.insert(0, path)
            self.current_index = 0

        self.current_image_path = path
        self.display_image(path)

    def display_image(self, path):
        self.gif_player.stop()  # 다른 이미지 열 때 GIF 재생 중단

        if not os.path.exists(path):
            QMessageBox.warning(self, "경고", "이미지를 찾을 수 없습니다.")
            return

        ext = get_file_extension(path)
        if ext == ".gif":
            if self.gif_player.load(path):
                self.gif_player.start()
            return

        img = cv2.imread(path)
        if img is None:
            QMessageBox.warning(self, "경고", "이미지를 열 수 없습니다.")
            return

        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        # 회전 및 반전
        if self.rotation_angle != 0 or self.flip_horizontal or self.flip_vertical:
            img = apply_rotation(img, self.rotation_angle)
            img = apply_flip(img, self.flip_horizontal, self.flip_vertical)

        # ✅ 업스케일링은 메뉴에서 직접 클릭 시에만 진행
        if self.enabled_upscale:
            self.start_upscaling(path)
            return

        # QImage로 변환
        h, w, ch = img.shape
        bytes_per_line = ch * w
        if not img.flags['C_CONTIGUOUS']:
            img = np.ascontiguousarray(img)
        qimg = QImage(img.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg)

        # ✅ 스케일 조정 (fit_to_window 활성화 여부에 따라)
        if self.fit_to_window:
            scaled = apply_scaling(pixmap, self.scale_factor, self.image_label.size())
        else:
            scaled = apply_scaling(pixmap, self.scale_factor)

        self.image_label.setPixmap(scaled)
        self.update_title()
        
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
        elif event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            self.open_thumbnail_dialog()

    def wheelEvent(self, event: QWheelEvent):
        if event.angleDelta().y() > 0:
            self.load_previous_image()
        else:
            self.load_next_image()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.gif_player and self.gif_frames:
            self.gif_player.fit_to_window = self.fit_to_window
            self.gif_player.scale_factor = self.scale_factor
            self.gif_player.update_frame()
        elif self.current_index != -1:
            self.refresh_image()

    def load_next_image(self):
        if self.current_index + 1 < len(self.image_list):
            self.current_index += 1
            self.open_image(self.image_list[self.current_index])

    def load_previous_image(self):
        if self.current_index > 0:
            self.current_index -= 1
            self.open_image(self.image_list[self.current_index])

    def open_thumbnail_dialog(self):
        if self.current_image_path:
            current_dir = os.path.dirname(self.current_image_path)
            dialog = ThumbnailDialog(current_dir, parent=self)
            dialog.exec_()
        else:
            QMessageBox.warning(self, "경고", "이미지 폴더를 찾을 수 없습니다.")

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
            img = cv2.imread(path)
            h, w = img.shape[:2] if img is not None else ("?", "?")
            msg = (
                f"파일명: {os.path.basename(path)}\n"
                f"크기: {size_kb:.2f} KB\n"
                f"해상도: {w} x {h}"
            )
            QMessageBox.information(self, "이미지 정보", msg)

    def start_upscaling(self, path):
        if not self.upscaler:
            QMessageBox.warning(self, "오류", "업스케일러가 초기화되지 않았습니다.")
            return

        cache_path = self.get_cached_path(path)

        if os.path.exists(cache_path):
            img = cv2.imread(cache_path)
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            self.on_upscale_done(img)
            return
        
        self.image_label.setText("업스케일링 중...")  # 로딩 표시
        self.upscale_worker = AsyncUpscaleWorker(path, self.upscaler, cache_path)
        self.upscale_worker.finished.connect(self.on_upscale_done)
        self.upscale_worker.start()

    def on_upscale_done(self, img):
        if img is None:
            QMessageBox.warning(self, "오류", "업스케일링 실패: 원본 이미지를 표시합니다.")
            self.display_image(self.current_image_path)
            return

        if not img.flags['C_CONTIGUOUS']:
            img = np.ascontiguousarray(img)
        h, w, ch = img.shape
        bytes_per_line = ch * w
        qimg = QImage(img.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg)

        if self.fit_to_window:
            scaled = apply_scaling(pixmap, self.scale_factor, self.image_label.size())
        else:
            scaled = apply_scaling(pixmap, self.scale_factor)

        self.image_label.setPixmap(scaled)
        self.update_title()
