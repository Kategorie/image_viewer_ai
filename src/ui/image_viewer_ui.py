import os
import cv2
import zipfile
import tempfile
import hashlib
import numpy as np
try:
    import imageio.v3 as iio
except ImportError:
    iio = None
from PIL import Image, ImageSequence

from PySide6.QtWidgets import (
    QMainWindow, QLabel, QFileDialog, QMenuBar, QDialog, QMenu, QMessageBox, QListWidget, QListWidgetItem, QVBoxLayout
)
from PySide6.QtGui import QPixmap, QImage, QAction, QWheelEvent, QContextMenuEvent, QActionGroup
from PySide6.QtCore import Qt, QSize, QTimer

from core.config_manager import ConfigManager
from core.upscaler import create_upscaler
from core.image_utils import is_image_file, extract_archive, get_file_extension
from ui.setting_dialog import SettingDialog

class ImageViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Image Viewer")
        self.setGeometry(100, 100, 1000, 700)

        self.config_manager = ConfigManager()
        self.upscaler = create_upscaler(self.config_manager)
        
        # 위젯 정의
        self.image_label = QLabel("이미지를 불러오세요", self)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.setCentralWidget(self.image_label)

        # 상태 변수 초기화 블록
        self.rotation_angle = 0  # ← 이미지 회전 각도 저장
        self.flip_horizontal = False
        self.flip_vertical = False
        self.upscale_enabled = False  # 업스케일링 ON/OFF 토글 상태
        self.current_image_path = None
        self.anim_timer = QTimer(self)
        
        self.image_list = []
        self.current_index = -1
        self.archive_tempdir = None
        self.scale_factor = self.config_manager.get("scale_factor", 1.0)
        self.fit_to_window = self.config_manager.get("fit_to_window", True)
        self.enabled_thumbnails = self.config_manager.get("enabled_thumbnails", True)
        self.enabled_upscale = self.config_manager.get("enabled_upscale", False)  # 업스케일링 ON/OFF 토글 상태

        self.gif_timer = QTimer()
        self.gif_frames = []
        self.gif_delays = []
        self.gif_index = 0

        self.init_menu_bar()
        self.integrate_settings_and_thumbnail_ui()

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
        fit_action.setChecked(self.config_manager.get("fit_to_window", True))
        fit_action.triggered.connect(self.toggle_fit_to_window)
        view_mode_group.addAction(fit_action)
        view_menu.addAction(fit_action)

        orig_action = QAction("원본 크기", self, checkable=True)
        orig_action.setChecked(not self.config_manager.get("fit_to_window", True))
        orig_action.triggered.connect(self.toggle_original_size)
        view_mode_group.addAction(orig_action)
        view_menu.addAction(orig_action)

        # 페이지 보기 방식 (단일 선택)
        page_mode_group = QActionGroup(self)
        page_mode_group.setExclusive(True)

        single_action = QAction("한장씩 보기", self, checkable=True)
        single_action.setChecked(self.config_manager.get("page_mode", "single") == "single")
        single_action.triggered.connect(lambda: self.set_page_mode("single"))
        page_mode_group.addAction(single_action)
        view_menu.addAction(single_action)

        double_action = QAction("두장씩 보기", self, checkable=True)
        double_action.setChecked(self.config_manager.get("page_mode", "single") == "double")
        double_action.triggered.connect(lambda: self.set_page_mode("double"))
        page_mode_group.addAction(double_action)
        view_menu.addAction(double_action)

        tools_menu = menu_bar.addMenu("도구")
        self.upscale_toggle = QAction("업스케일 사용", self, checkable=True)
        self.upscale_toggle.setChecked(self.enabled_upscale)
        self.upscale_toggle.triggered.connect(self.toggle_upscale)
        tools_menu.addAction(self.upscale_toggle)

        thumbnail_dialog_action = QAction("썸네일 보기", self)
        thumbnail_dialog_action.triggered.connect(self.open_thumbnail_dialog)
        tools_menu.addAction(thumbnail_dialog_action)

    # 페이지 보기 적용 함수
    def set_page_mode(self, mode):
        self.config_manager["page_mode"] = mode
        self.refresh_image()

    def toggle_upscale(self):
        self.upscale_enabled = not self.upscale_enabled
        self.upscale_toggle.setChecked(self.upscale_enabled)
        self.config_manager.set("enabled_upscale", self.upscale_enabled)

    def toggle_fit_to_window(self, checked):
        self.fit_to_window = checked
        self.config_manager.set("fit_to_window", self.fit_to_window)
        self.refresh_image()

    def toggle_original_size(self, checked):
        self.fit_to_window = not checked
        self.config_manager.set("fit_to_window", self.fit_to_window)
        self.refresh_image()

    def refresh_image(self):
        if self.current_index >= 0:
            self.open_image(self.image_list[self.current_index])

    def open_file_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "이미지/압축 파일 열기",
            "",
            "Images/Archives (*.png *.jpg *.jpeg *.bmp *.gif *.zip *.cbz)"
        )
        if not file_path:
            return

        file_path = os.path.abspath(file_path)
        ext = os.path.splitext(file_path)[1].lower()

        if ext in [".zip", ".cbz"]:
            try:
                self.image_list = extract_archive(file_path)
                if not self.image_list:
                    QMessageBox.information(self, "알림", "압축 파일 내에 이미지가 없습니다.")
                    return
                self.current_index = 0
                self.open_image(self.image_list[0])
            except Exception as e:
                QMessageBox.critical(self, "압축 해제 오류", str(e))
            return

        # 일반 이미지 파일 처리
        folder = os.path.dirname(file_path)
        self.image_list = sorted([
            os.path.abspath(os.path.join(folder, f))
            for f in os.listdir(folder)
            if f.lower().endswith((".jpg", ".jpeg", ".png", ".bmp", ".gif"))
        ])

        if file_path in self.image_list:
            self.current_index = self.image_list.index(file_path)
            self.open_image(file_path)
        else:
            QMessageBox.warning(self, "경고", "이미지가 현재 폴더 내에 없습니다.")
            
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
        """
        이미지를 열고 목록에 등록하며 표시하는 함수.
        이미지 폴더를 기준으로 이미지 리스트를 재구성하고 현재 인덱스를 설정한다.
        """
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
        """
        실제 이미지를 화면에 표시하는 핵심 처리 함수.
        - 업스케일링 (GIF 제외)
        - 회전, 반전
        - gif 여부에 따른 분기
        """
        # GIF 재생 중지
        if self.anim_timer.isActive():
            self.anim_timer.stop()
        try:
            self.anim_timer.timeout.disconnect()
        except Exception:
            pass

        if not os.path.exists(path):
            QMessageBox.warning(self, "경고", "이미지를 찾을 수 없습니다.")
            return

        ext = get_file_extension(path)
        if ext == ".gif":
            self.play_gif(path)
            return

        img = cv2.imread(path)
        if img is None:
            QMessageBox.warning(self, "경고", "이미지를 열 수 없습니다.")
            return

        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        # 회전 및 반전
        if self.rotation_angle != 0:
            rot_map = {90: cv2.ROTATE_90_CLOCKWISE, 180: cv2.ROTATE_180, 270: cv2.ROTATE_90_COUNTERCLOCKWISE}
            img = cv2.rotate(img, rot_map.get(self.rotation_angle, 0))
        if self.flip_horizontal:
            img = cv2.flip(img, 1)
        if self.flip_vertical:
            img = cv2.flip(img, 0)

        # 업스케일 적용 (GIF는 제외)
        if self.upscale_enabled and self.upscaler:
            try:
                cache_path = self.get_cached_path(path)
                if os.path.exists(cache_path):
                    img = cv2.imread(cache_path)
                    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                else:
                    output, _ = self.upscaler.enhance(img)
                    cv2.imwrite(cache_path, output)
                    img = output
            except Exception as e:
                print(f"[!] 업스케일링 실패: {e}")

        h, w, ch = img.shape
        bytes_per_line = ch * w
        if not img.flags['C_CONTIGUOUS']:
            img = np.ascontiguousarray(img)
        qimg = QImage(img.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg)

        if self.fit_to_window:
            scaled = pixmap.scaled(self.image_label.size(), Qt.KeepAspectRatio)
        else:
            scaled = pixmap.scaled(pixmap.size() * self.scale_factor, Qt.KeepAspectRatio)

        self.image_label.setPixmap(scaled)
        self.update_title()

    def get_cached_path(self, image_path: str) -> str:
        name_hash = hashlib.md5(image_path.encode()).hexdigest()
        ext = os.path.splitext(image_path)[1].lower()
        cache_name = f"{name_hash}{ext}"
        return os.path.join("src/cache", cache_name)

    def play_gif(self, path):
        """
        gif 이미지 재생을 처리하는 함수 (프레임 기반 애니메이션)
        """
        if iio is None:
            QMessageBox.warning(self, "라이브러리 누락", "GIF 재생을 위해 imageio가 필요합니다.")
            return
        
        self.gif_frames = []
        self.gif_durations = []

        try:
            for frame in iio.imiter(path, plugin="pillow", mode="RGB"):
                self.gif_frames.append(frame)
            meta = iio.immeta(path, plugin="pillow")
            duration = meta.get("duration", 100)
            self.gif_durations = [duration for _ in self.gif_frames]
        except Exception as e:
            print("[GIF 오류]", e)
            return

        self.current_gif_index = 0
        if not self.gif_frames:
            return

        # ✨ 프레임 타이머 안전하게 초기화
        if self.anim_timer.isActive():
            self.anim_timer.stop()
        try: # 깔끔한 연결 해제
            self.anim_timer.timeout.disconnect(self.update_gif_frame)
        except (RuntimeError, TypeError):
            pass
        
        self.anim_timer.timeout.connect(self.update_gif_frame)
        self.anim_timer.start(self.gif_durations[0])
    
    def update_gif_frame(self):
        """
        GIF 프레임을 순차적으로 표시하는 타이머 함수.
        프레임 재생 속도는 프레임당 duration에 맞춰 자동 설정됨.
        """
        if not self.gif_frames:
            return

        frame = self.gif_frames[self.current_gif_index]
        h, w, ch = frame.shape
        bytes_per_line = ch * w
        qimg = QImage(frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg)

        if self.fit_to_window:
            scaled = pixmap.scaled(self.image_label.size(), Qt.KeepAspectRatio)
        else:
            scaled = pixmap.scaled(pixmap.size() * self.scale_factor, Qt.KeepAspectRatio)

        self.image_label.setPixmap(scaled)

        # 다음 프레임 준비
        self.current_gif_index = (self.current_gif_index + 1) % len(self.gif_frames)
        next_duration = self.gif_durations[self.current_gif_index]
        self.anim_timer.start(next_duration)

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
        elif event.key() == Qt.Key_Return and self.current_image_path:
            abs_list = [os.path.abspath(p) for p in self.image_list]
            current = os.path.abspath(self.current_image_path)
            if current in abs_list:
                self.open_thumbnail_dialog()
    
    def open_thumbnail_dialog(self, force=False):
        if not self.enabled_thumbnails and not force:
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
            if img is None:
                continue  # 잘못된 이미지 패스
            
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

    def integrate_settings_and_thumbnail_ui(self):
        """Viewer 클래스 내부에 통합 메서드로 삽입하면 좋음"""

        # 메뉴 추가
        settings_menu = self.menuBar().addMenu("설정")
        setting_action = QAction("환경 설정", self)
        settings_menu.addAction(setting_action)
        setting_action.triggered.connect(self.open_setting_dialog)

        tools_menu = self.menuBar().addMenu("도구")
        thumb_action = QAction("썸네일 보기", self, checkable=True)
        thumb_action.setChecked(self.config_manager.get("enabled_thumbnails", False))
        thumb_action.toggled.connect(self.toggle_thumbnails)
        tools_menu.addAction(thumb_action)

        # 키 이벤트 오버라이드
        original_keyPressEvent = self.keyPressEvent
        def new_keyPressEvent(event):
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                self.open_thumbnail_dialog(force=True)
            elif event.key() == Qt.Key_Escape:
                self.close()
            else:
                original_keyPressEvent(event)
        self.keyPressEvent = new_keyPressEvent

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

    def open_setting_dialog(self):
        dlg = SettingDialog(self.config_manager.get_all(), self)
        if dlg.exec():
            updated = dlg.get_values()
            self.config_manager.update(updated)
            self.upscaler = create_upscaler(self.config_manager)
            QMessageBox.information(self, "적용 완료", "설정이 저장되었습니다.")

    def toggle_thumbnails(self, checked):
        self.config_manager.set("enabled_thumbnails", checked)

    def reset_settings(self):
        # 1. 기본값 덮어쓰기
        self.config_manager.set("enabled_upscale", False)
        self.config_manager.set("enabled_thumbnails", True)
        self.config_manager.set("fit_to_window", True)
        self.config_manager.set("scale_factor", 1.0)
        self.config_manager.set("tile", 128)
        self.config_manager.set("scale", 4)
        self.config_manager.set("model_path", "src/models/RealESRNET_x4plus.pth")
        self.config_manager.set("half", False)
        self.config_manager.set("page_mode", "single")

        # 2. 반영
        self.upscale_enabled = False
        self.enable_thumbnails = True
        self.fit_to_window = True
        self.scale_factor = 1.0
        self.page_mode = "single"

        # 3. 업스케일러 재생성
        self.upscaler = create_upscaler(self.config_manager)

        QMessageBox.information(self, "초기화", "기본 설정으로 초기화되었습니다.")
