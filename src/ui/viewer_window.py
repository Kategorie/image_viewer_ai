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
    QMainWindow, QLabel, QFileDialog, QMenuBar, QMenu, QMessageBox, QToolBar, QSizePolicy, QCheckBox
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
        self.upscale_queue = []
        self.upscale_processing = False

        self.upscaler = create_upscaler("real-esrgan", self.settings)

        self.image_label = QLabel("이미지를 불러오세요", self)
        self.image_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.image_label.setScaledContents(True)
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

        # 툴바에 체크박스 추가
        auto_hide_toolbar = QToolBar()
        auto_hide_toolbar.setMovable(False)
        auto_hide_checkbox = QCheckBox("UI 자동 숨김")
        auto_hide_checkbox.setChecked(False)
        auto_hide_checkbox.toggled.connect(self.toggle_ui_visibility)
        auto_hide_toolbar.addWidget(auto_hide_checkbox)
        self.addToolBar(Qt.TopToolBarArea, auto_hide_toolbar)
    

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
        self.upscale_action.triggered.connect(lambda: self.request_upscale(self.current_image_path))
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
        if checked and self.current_image_path:
            dialog = ThumbnailDialog(os.path.dirname(self.current_image_path), parent=self)
            dialog.exec()
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

        self.current_index = max(0, min(self.current_index, len(self.image_list) - 1))
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
            self.update_title()
            return

        img = cv2.imread(path)
        if img is None:
            QMessageBox.warning(self, "경고", "이미지를 열 수 없습니다.")
            return

        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        # 두 장 보기 조건: 페이지 모드 + 너비 제한
        if self.settings.page_mode == "double" and img.shape[1] < 1200:
            if self.current_index + 1 < len(self.image_list):
                next_path = self.image_list[self.current_index + 1]
                next_img = cv2.imread(next_path)
                if next_img is not None:
                    next_img = cv2.cvtColor(next_img, cv2.COLOR_BGR2RGB)
                    if next_img.shape[0] != img.shape[0]:
                        next_img = cv2.resize(next_img, (int(next_img.shape[1] * (img.shape[0] / next_img.shape[0])), img.shape[0]))
                    img = np.concatenate((img, next_img), axis=1)
                    self.setWindowTitle(self.windowTitle() + " [2장 보기]")


        # 회전 및 반전
        if self.rotation_angle != 0 or self.flip_horizontal or self.flip_vertical:
            img = apply_rotation(img, self.rotation_angle)
            img = apply_flip(img, self.flip_horizontal, self.flip_vertical)

        # ✅ 업스케일링은 메뉴에서 직접 클릭 시에만 진행
        if self.enabled_upscale:
            self.request_upscale(path)
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
        if not hasattr(self, "list_widget") or self.list_widget is None:
            return
        
        if self.gif_player and self.gif_frames:
            self.gif_player.fit_to_window = self.fit_to_window
            self.gif_player.scale_factor = self.scale_factor
            self.gif_player.update_frame()
        elif self.current_index != -1:
            self.refresh_image()

    def load_next_image(self):
        step = 2 if self.settings.page_mode == "double" else 1
        if self.current_index + step < len(self.image_list):
            self.current_index += step
            self.open_image(self.image_list[self.current_index])

    def load_previous_image(self):
        step = 2 if self.settings.page_mode == "double" else 1
        if self.current_index - step >= 0:
            self.current_index -= step
            self.open_image(self.image_list[self.current_index])

    def open_thumbnail_dialog(self):
        if self.current_image_path:
            current_dir = os.path.dirname(self.current_image_path)
            dialog = ThumbnailDialog(current_dir, parent=self)
            dialog.imageSelected.connect(self.show_thumbnail)
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

        # 두 장 보기 조건: 페이지 모드 + 너비 제한
        if self.settings.page_mode == "double" and img.shape[1] < 1200:
            if self.current_index + 1 < len(self.image_list):
                next_path = self.image_list[self.current_index + 1]
                next_img = cv2.imread(next_path)
                if next_img is not None:
                    next_img = cv2.cvtColor(next_img, cv2.COLOR_BGR2RGB)
                    if next_img.shape[0] != img.shape[0]:
                        next_img = cv2.resize(next_img, (int(next_img.shape[1] * (img.shape[0] / next_img.shape[0])), img.shape[0]))
                    img = np.concatenate((img, next_img), axis=1)
                    self.setWindowTitle(self.windowTitle() + " [2장 보기]")

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
        self.upscale_processing = False
        self._process_next_upscale()

    def request_upscale(self, path):
        if not self.settings.sequential_upscale:
            self.start_upscaling(path)
            return
        
        if path not in self.upscale_queue:
            self.upscale_queue.append(path)

        if not self.upscale_processing:
            self._process_next_upscale()

    def _process_next_upscale(self):
        if not self.upscale_queue:
            self.upscale_processing = False
            return
        self.upscale_processing = True
        next_path = self.upscale_queue.pop(0)
        self.start_upscaling(next_path)

    def load_image(self, path):
        self.open_image(path)

    def toggle_ui_visibility(self, checked):
        self.auto_ui_hidden = checked
        self.menuBar().setVisible(not checked)
        self.setWindowFlag(Qt.FramelessWindowHint, checked)
        self.setMinimumSize(200, 150)
        self.show()
        self.refresh_image()

    def mouseMoveEvent(self, event):
        if getattr(self, 'auto_ui_hidden', False):
            if event.pos().y() < 10:
                self.menuBar().setVisible(True)
            else:
                self.menuBar().setVisible(False)
        super().mouseMoveEvent(event)

    def closeEvent(self, event): 
        # 윈도우가 닫히기 직전에 호출되는 이벤트 핸들러
        # GIF 재생 중일 경우 self.gif_player.stop()으로 재생 정지 처리
        if self.gif_player:
            self.gif_player.stop()
        event.accept()

    def showEvent(self, event):
        # 윈도우가 처음 열리거나 .show()로 다시 표시될 때 호출됨
        # GIF 플레이어 관련 정보를 다시 적용 후 프레임 갱신 (update_frame())
        super().showEvent(event)
        if hasattr(self, "gif_player") and self.gif_player:
            self.gif_player.fit_to_window = self.fit_to_window
            self.gif_player.scale_factor = self.scale_factor
            self.gif_player.update_frame()

    def hideEvent(self, event):
        super().hideEvent(event)
        if self.gif_player:
            self.gif_player.stop()

    def show_thumbnail(self, path):
        # 외부에서 경로를 받아 특정 이미지를 썸네일처럼 보여주는 용도
        # 이미지 로드 후 image_label에 표시 (현재 사이즈에 맞춰 scaled())
        if not os.path.exists(path):
            QMessageBox.warning(self, "경고", "썸네일을 찾을 수 없습니다.")
            return

        img = cv2.imread(path)
        if img is None:
            QMessageBox.warning(self, "경고", "썸네일을 열 수 없습니다.")
            return

        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        h, w, ch = img.shape
        bytes_per_line = ch * w
        qimg = QImage(img.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg)

        self.image_label.setPixmap(pixmap.scaled(self.image_label.size(), Qt.KeepAspectRatio))

    def extract_archive(self, path):
        #.zip, .cbz 등 압축 파일의 내용을 임시 폴더에 풀고, 이미지 리스트로 갱신
        # archive_tempdir를 사용해 중복 압축 해제 방지 및 기존 캐시 삭제
        if not os.path.exists(path):
            QMessageBox.warning(self, "경고", "압축 파일을 찾을 수 없습니다.")
            return

        if self.archive_tempdir:
            extract_archive(self.archive_tempdir)
            self.archive_tempdir = None
        else:
            self.archive_tempdir = extract_archive(path)
            if not self.archive_tempdir:
                QMessageBox.warning(self, "경고", "압축 해제에 실패했습니다.")
                return

        self.image_list = sorted([
            os.path.join(self.archive_tempdir, f) for f in os.listdir(self.archive_tempdir)
            if is_image_file(f)
        ])
        self.current_index = 0
        self.open_image(self.image_list[self.current_index])

    