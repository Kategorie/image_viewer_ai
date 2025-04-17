import sys
import os
import json
import mimetypes
import hashlib
import threading

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QLabel, QFileDialog, QVBoxLayout,
    QWidget, QPushButton, QHBoxLayout, QMenu, QToolBar, QMessageBox, QDialog, QListWidget, QListWidgetItem, QCheckBox, QInputDialog, QFileDialog
)
from PySide6.QtGui import QPixmap, QImage, QAction, QKeySequence, QContextMenuEvent, QTransform, QDragEnterEvent, QDropEvent, QIcon
from PySide6.QtCore import Qt, QSize, QTimer
import cv2
import numpy as np
from basicsr.archs.rrdbnet_arch import RRDBNet
from realesrgan import RealESRGANer

CONFIG_PATH = "config/viewer_config.json"
CACHE_DIR = "src/cache"
class ImageViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Image Viewer with Upscale")
        self.setGeometry(100, 100, 800, 600)

        self.image_label = QLabel("이미지를 불러오세요", self)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.setCentralWidget(self.image_label)

        self.setAcceptDrops(True)

        self.current_image_path = None
        self.upscale_enabled = False
        self.fit_to_window = True
        self.scale_factor = 1.0
        self.rotation_angle = 0
        self.flip_horizontal = False
        self.flip_vertical = False
        self.model = self.init_upscaler()

        self.image_list = []
        self.current_index = -1
        self.anim_timer = QTimer(self)
        self.gif_frames = []
        self.current_gif_index = 0

        os.makedirs(CACHE_DIR, exist_ok=True)
        self.create_menu()
        self.create_shortcuts()
        self.load_settings()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()  # ⎋ 종료
        elif event.key() in [Qt.Key_Left, Qt.Key_Up]:
            self.load_previous_image()
        elif event.key() in [Qt.Key_Right, Qt.Key_Down]:
            self.load_next_image()
        elif event.key() == Qt.Key_Return and self.current_image_path:
            self.show_image_list_dialog()

    def show_image_list_dialog(self):
        folder = os.path.dirname(self.current_image_path)
        image_files = sorted([
            f for f in os.listdir(folder)
            if f.lower().endswith((".jpg", ".jpeg", ".png", ".bmp", ".gif"))
        ])
        current_file = os.path.basename(self.current_image_path)

        dialog = QDialog(self)
        dialog.setWindowTitle("이미지 선택")
        layout = QVBoxLayout(dialog)

        thumb_cache_dir = os.path.join("src/cache", "thumbnails")
        os.makedirs(thumb_cache_dir, exist_ok=True)

        # 썸네일 보기 체크박스
        checkbox = QCheckBox("썸네일 보기", dialog)
        checkbox.setChecked(self.config.get("enable_thumbnails", True))
        layout.addWidget(checkbox)

        list_widget = QListWidget(dialog)
        list_widget.setIconSize(QSize(100, 100))

        SHOW_THUMBNAIL = checkbox.isChecked() and len(image_files) <= 100

        for f in image_files:
            item = QListWidgetItem(f)
            image_path = os.path.join(folder, f)
            if SHOW_THUMBNAIL:
                hash_name = hashlib.md5(image_path.encode()).hexdigest() + ".png"
                thumb_path = os.path.join(thumb_cache_dir, hash_name)
                if os.path.exists(thumb_path):
                    pixmap = QPixmap(thumb_path)
                else:
                    pixmap = QPixmap(image_path).scaled(100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    pixmap.save(thumb_path)
                item.setIcon(QIcon(pixmap))
            list_widget.addItem(item)

        current_row = image_files.index(current_file)
        list_widget.setCurrentRow(current_row)

        def load_selected():
            selected = list_widget.currentItem()
            if selected:
                full_path = os.path.join(folder, selected.text())
                self.open_image(full_path)
                dialog.accept()

        def keyPressEvent_inner(event):
            if event.key() == Qt.Key_Return:
                load_selected()
        list_widget.keyPressEvent = keyPressEvent_inner

        layout.addWidget(list_widget)
        dialog.setLayout(layout)
        dialog.resize(520, 450)
        dialog.exec()

        # 저장된 체크박스 상태 반영
        self.config["enable_thumbnails"] = checkbox.isChecked()
        self.save_settings()
        
    def load_settings(self):
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, 'r') as f:
                data = json.load(f)
                self.fit_to_window = data.get("fit_to_window", True)
                self.scale_factor = 1.0 if self.fit_to_window else data.get("scale_factor", 1.0)

    def save_settings(self):
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, 'w') as f:
            json.dump({
                "fit_to_window": self.fit_to_window,
                "scale_factor": self.scale_factor
            }, f)

    def init_upscaler(self):
        model_path = "src/models/RealESRNET_x4plus.pth"
        model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64,
                        num_block=23, num_grow_ch=32, scale=4)
        return RealESRGANer(
            scale=self.config.get("scale", 4),
            model_path=self.config.get("model_path", "src/models/RealESRNET_x4plus.pth"),
            model=model,
            tile=self.config.get("tile", 128),  # ⬅️ tile 사용
            tile_pad=4,
            pre_pad=0,
            half=self.config.get("half", False)
        )

    def get_cache_path(self, path):
        base_name = os.path.basename(path)
        file_hash = hashlib.md5(path.encode()).hexdigest()
        return os.path.join(CACHE_DIR, f"{file_hash}_{base_name}")

    def check_cache_exists(self, path):
        return os.path.exists(self.get_cache_path(path))

    def load_from_cache(self, path):
        return cv2.imread(self.get_cache_path(path))

    def save_to_cache(self, path, image):
        cv2.imwrite(self.get_cache_path(path), image)

    def display_image(self, path):
        if path.lower().endswith(".gif"):
            self.play_gif(path)
            return

        self.anim_timer.stop()
        self.gif_frames = []

        if self.upscale_enabled and self.check_cache_exists(path):
            img = self.load_from_cache(path)
        else:
            img = cv2.imread(path)
            if self.upscale_enabled:
                img, _ = self.model.enhance(img)
                self.save_to_cache(path, img)

        if self.flip_horizontal:
            img = cv2.flip(img, 1)
        if self.flip_vertical:
            img = cv2.flip(img, 0)
        if self.rotation_angle != 0:
            rotate_code = {
                90: cv2.ROTATE_90_CLOCKWISE,
                180: cv2.ROTATE_180,
                270: cv2.ROTATE_90_COUNTERCLOCKWISE
            }.get(self.rotation_angle % 360, None)
            if rotate_code:
                img = cv2.rotate(img, rotate_code)

        self.last_displayed_image = img

        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        h, w, ch = img.shape
        bytes_per_line = ch * w
        qt_image = QImage(img.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qt_image)

        if self.fit_to_window:
            scaled = pixmap.scaled(self.image_label.size(), Qt.KeepAspectRatio)
        else:
            scaled = pixmap.scaled(pixmap.size() * self.scale_factor, Qt.KeepAspectRatio)

        self.image_label.setPixmap(scaled)
        self.save_settings()

    def create_menu(self):
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("파일")
        view_menu = menu_bar.addMenu("보기")
        settings_menu = menu_bar.addMenu("설정")

        open_action = QAction("열기", self)
        open_action.triggered.connect(self.open_file_dialog)
        file_menu.addAction(open_action)

        upscale_toggle = QAction("업스케일 사용", self, checkable=True)
        upscale_toggle.setChecked(self.upscale_enabled)
        upscale_toggle.triggered.connect(self.toggle_upscale)
        view_menu.addAction(upscale_toggle)

        thumbnail_toggle = QAction("썸네일 보기", self, checkable=True)
        thumbnail_toggle.setChecked(self.config.get("enable_thumbnails", True))
        thumbnail_toggle.triggered.connect(self.toggle_thumbnail)
        view_menu.addAction(thumbnail_toggle)

        tile_action = QAction("Tile 크기 (64/128/256)", self)
        tile_action.triggered.connect(lambda: self.set_config_option("tile", [64, 128, 256]))
        scale_action = QAction("Scale 배율 (2/4)", self)
        scale_action.triggered.connect(lambda: self.set_config_option("scale", [2, 4]))
        model_action = QAction("모델 변경", self)
        model_action.triggered.connect(self.select_model_file)

        settings_menu.addAction(tile_action)
        settings_menu.addAction(scale_action)
        settings_menu.addAction(model_action)

    def create_shortcuts(self):
        next_action = QAction(self)
        next_action.setShortcut(QKeySequence(Qt.Key_Right))
        next_action.triggered.connect(self.load_next_image)
        self.addAction(next_action)

        prev_action = QAction(self)
        prev_action.setShortcut(QKeySequence(Qt.Key_Left))
        prev_action.triggered.connect(self.load_previous_image)
        self.addAction(prev_action)

    def update_window_title(self):
        if not self.current_image_path:
            self.setWindowTitle("AI Image Viewer")
            return
            
        folder_name = os.path.basename(os.path.dirname(self.current_image_path))
        file_name = os.path.basename(self.current_image_path)
        total = len(self.image_list)
        index = self.current_index + 1 if self.current_index >= 0 else "?"
        self.setWindowTitle(f"[{index}/{total}] {file_name} - {folder_name}")

    def toggle_upscale(self):
        self.upscale_enabled = not self.upscale_enabled
        if self.current_image_path:
            self.display_image(self.current_image_path)

    def preload_upscaled_image(self, index):
        if 0 <= index < len(self.image_list):
            path = self.image_list[index]
            cache_path = self.get_cache_path(path)
            if not os.path.exists(cache_path):
                threading.Thread(target=self.process_upscale, args=(path, cache_path), daemon=True).start()
    
    def set_config_option(self, key, options):
        val, ok = QInputDialog.getItem(self, f"{key} 설정", f"{key} 선택:", [str(o) for o in options], editable=False)
        if ok:
            self.config[key] = int(val)
            self.save_settings()
            QMessageBox.information(self, "설정 적용됨", f"{key} 값이 {val}로 설정되었습니다.\n프로그램을 재시작하세요.")
        def process_upscale(self, img_path, save_path):
            img = cv2.imread(img_path, cv2.IMREAD_COLOR)
            if img is None:
                return
            output, _ = self.upscaler.enhance(img)
            cv2.imwrite(save_path, output)

    def open_image(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "이미지 열기", "", "Image Files (*.png *.jpg *.jpeg *.bmp *.gif)")
        if file_path:
            folder = os.path.dirname(file_path)
            self.image_list = [os.path.abspath(os.path.join(folder, f)) for f in os.listdir(folder)
                               if f.lower().endswith((".jpg", ".jpeg", ".png", ".bmp", ".gif"))]
            self.image_list.sort()
            abs_file_path = os.path.abspath(file_path)
            if abs_file_path in self.image_list:
                self.current_index = self.image_list.index(abs_file_path)
                self.current_image_path = abs_file_path
                self.display_image(abs_file_path)

    def save_image(self):
        if hasattr(self, 'last_displayed_image') and self.last_displayed_image is not None:
            save_path, _ = QFileDialog.getSaveFileName(self, "이미지 저장", "upscaled.png",
                                                       "PNG Files (*.png);;JPEG Files (*.jpg *.jpeg)")
            if save_path:
                cv2.imwrite(save_path, self.last_displayed_image)

    def show_image_info(self):
        if self.current_image_path and os.path.exists(self.current_image_path):
            file_info = os.stat(self.current_image_path)
            file_size_kb = round(file_info.st_size / 1024, 2)
            mime_type, _ = mimetypes.guess_type(self.current_image_path)

            text = (
                f"파일명: {os.path.basename(self.current_image_path)}\n"
                f"경로: {self.current_image_path}\n"
                f"용량: {file_size_kb} KB\n"
                f"유형: {mime_type or '알 수 없음'}"
            )
            QMessageBox.information(self, "이미지 정보", text)
    
    def select_model_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "모델 선택", "src/models", "Model Files (*.pth)")
        if path:
            self.config["model_path"] = path
            self.save_settings()
            QMessageBox.information(self, "모델 선택됨", f"{os.path.basename(path)} 모델이 설정되었습니다.\n프로그램을 재시작하세요.")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.fit_to_window and self.current_image_path:
            self.display_image(self.current_image_path)

    def wheelEvent(self, event):
        # ✨ 통합됨: Ctrl+휠 → 확대/축소, 일반 휠 → 이미지 탐색
        modifiers = QApplication.keyboardModifiers()
        if modifiers == Qt.ControlModifier:
            delta = event.angleDelta().y()
            factor = 1.1 if delta > 0 else 0.9
            self.scale_factor *= factor
            if self.current_image_path and not self.fit_to_window:
                self.display_image(self.current_image_path)
        else:
            if event.angleDelta().y() > 0:
                self.load_previous_image()
            else:
                self.load_next_image()

    def play_gif(self, path):
        cap = cv2.VideoCapture(path)
        self.gif_frames = []
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            self.gif_frames.append(frame_rgb)
        cap.release()

        if not self.gif_frames:
            return

        self.current_gif_index = 0
        interval = max(20, int(1000 / len(self.gif_frames)))  # 프레임 수 기반 속도
        self.anim_timer.timeout.disconnect()
        self.anim_timer.timeout.connect(self.update_gif_frame)
        self.anim_timer.start(interval)

    def update_gif_frame(self):
        frame = self.gif_frames[self.current_gif_index]
        h, w, ch = frame.shape
        bytes_per_line = ch * w
        qt_image = QImage(frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qt_image)

        if self.fit_to_window:
            scaled = pixmap.scaled(self.image_label.size(), Qt.KeepAspectRatio)
        else:
            scaled = pixmap.scaled(pixmap.size() * self.scale_factor, Qt.KeepAspectRatio)

        self.image_label.setPixmap(scaled)
        self.current_gif_index = (self.current_gif_index + 1) % len(self.gif_frames)

    def set_fit_to_window(self):
        self.fit_to_window = True
        self.original_action.setChecked(False)
        if self.current_image_path:
            self.display_image(self.current_image_path)

    def set_original_size(self):
        self.fit_to_window = False
        self.scale_factor = 1.0
        self.fit_action.setChecked(False)
        if self.current_image_path:
            self.display_image(self.current_image_path)

    def rotate_image(self):
        self.rotation_angle = (self.rotation_angle + 90) % 360
        if self.current_image_path:
            self.display_image(self.current_image_path)

    def flip_horizontal_image(self):
        self.flip_horizontal = not self.flip_horizontal
        if self.current_image_path:
            self.display_image(self.current_image_path)

    def flip_vertical_image(self):
        self.flip_vertical = not self.flip_vertical
        if self.current_image_path:
            self.display_image(self.current_image_path)

    def load_next_image(self):
        if self.image_list and self.current_index < len(self.image_list) - 1:
            self.current_index += 1
            self.current_image_path = self.image_list[self.current_index]
            self.display_image(self.current_image_path)

    def load_previous_image(self):
        if self.image_list and self.current_index > 0:
            self.current_index -= 1
            self.current_image_path = self.image_list[self.current_index]
            self.display_image(self.current_image_path)

    def contextMenuEvent(self, event: QContextMenuEvent):
        context_menu = QMenu(self)

        upscale_toggle_action = QAction("업스케일 적용 토글 (현재: {})".format("ON" if self.upscale_enabled else "OFF"), self)
        upscale_toggle_action.triggered.connect(self.toggle_upscale)
        context_menu.addAction(upscale_toggle_action)

        context_menu.exec(event.globalPos())

    def set_fit_to_window(self):
        self.fit_to_window = True
        self.original_action.setChecked(False)
        if self.current_image_path:
            self.display_image(self.current_image_path)

    def set_original_size(self):
        self.fit_to_window = False
        self.scale_factor = 1.0
        self.fit_action.setChecked(False)
        if self.current_image_path:
            self.display_image(self.current_image_path)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    viewer = ImageViewer()
    viewer.show()
    sys.exit(app.exec())
