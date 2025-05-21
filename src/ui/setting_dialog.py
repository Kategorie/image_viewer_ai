from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QWidget, QLabel, QSpinBox, QLineEdit, QCheckBox, QPushButton,
    QFileDialog, QStackedWidget, QComboBox
)
from config.settings_loader import AppSettings
from dataclasses import replace

class SettingDialog(QDialog):
    def __init__(self, settings: AppSettings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("환경 설정")
        self.resize(600, 400)

        self.settings = settings
        self.modified = replace(settings)

        main_layout = QHBoxLayout(self)
        self.section_list = QListWidget()
        self.stack = QStackedWidget()

        main_layout.addWidget(self.section_list, 1)
        main_layout.addWidget(self.stack, 3)

        self.setup_sections()
        self.section_list.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.section_list.setCurrentRow(0)

        # 왼쪽 하단 버튼
        button_layout = QVBoxLayout()
        self.apply_button = QPushButton("적용")
        self.reset_button = QPushButton("초기화")
        self.apply_button.clicked.connect(self.accept)
        self.reset_button.clicked.connect(self.reset_defaults)
        button_layout.addWidget(self.apply_button)
        button_layout.addWidget(self.reset_button)
        button_layout.addStretch()
        main_layout.addLayout(button_layout)

    def setup_sections(self):
        # 일반 설정
        general = QWidget()
        g_layout = QVBoxLayout(general)

        self.chk_thumbnails = QCheckBox("썸네일 보기")
        self.chk_thumbnails.setChecked(self.settings.get("enabled_thumbnails", False))
        self.chk_upscale = QCheckBox("업스케일링 사용")
        self.chk_upscale.setChecked(self.settings.get("enabled_upscale", False))

        g_layout.addWidget(self.chk_thumbnails)
        g_layout.addWidget(self.chk_upscale)
        g_layout.addStretch()
        self.stack.addWidget(general)
        self.section_list.addItem(QListWidgetItem("일반"))

        # 영상 처리
        processing = QWidget()
        p_layout = QVBoxLayout(processing)

        self.spn_scale = QSpinBox()
        self.spn_scale.setRange(1, 8)
        self.spn_scale.setValue(self.settings.get("scale", 4))
        self.spn_tile = QSpinBox()
        self.spn_tile.setRange(0, 1024)
        self.spn_tile.setValue(self.settings.get("tile", 128))

        self.model_path = QLineEdit(self.settings.get("model_path", ""))
        self.btn_model_path = QPushButton("모델 경로 찾기")
        self.btn_model_path.clicked.connect(self.browse_model)

        p_layout.addWidget(QLabel("업스케일 배율 (scale)"))
        p_layout.addWidget(self.spn_scale)
        p_layout.addWidget(QLabel("타일 사이즈 (tile)"))
        p_layout.addWidget(self.spn_tile)
        p_layout.addWidget(QLabel("모델 파일 경로"))
        p_layout.addWidget(self.model_path)
        p_layout.addWidget(self.btn_model_path)
        p_layout.addStretch()
        self.stack.addWidget(processing)
        self.section_list.addItem(QListWidgetItem("영상처리"))

        # 인터페이스
        interface = QWidget()
        i_layout = QVBoxLayout(interface)

        self.cmb_theme = QComboBox()
        self.cmb_theme.addItems(["light", "dark"])
        self.cmb_theme.setCurrentText(self.settings.get("theme", "light"))

        self.spn_font = QSpinBox()
        self.spn_font.setRange(8, 20)
        self.spn_font.setValue(self.settings.get("font_size", 10))

        self.cmb_lang = QComboBox()
        self.cmb_lang.addItems(["ko", "en"])
        self.cmb_lang.setCurrentText(self.settings.get("language", "ko"))

        i_layout.addWidget(QLabel("테마"))
        i_layout.addWidget(self.cmb_theme)
        i_layout.addWidget(QLabel("폰트 크기"))
        i_layout.addWidget(self.spn_font)
        i_layout.addWidget(QLabel("언어"))
        i_layout.addWidget(self.cmb_lang)
        i_layout.addStretch()

        self.stack.addWidget(interface)
        self.section_list.addItem(QListWidgetItem("인터페이스"))

    def browse_model(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "모델 파일 선택", "", "PyTorch Models (*.pth)")
        if file_path:
            self.model_path.setText(file_path)

    def get_values(self) -> dict:
        return {
            "enabled_thumbnails": self.chk_thumbnails.isChecked(),
            "enabled_upscale": self.chk_upscale.isChecked(),
            "scale": self.spn_scale.value(),
            "tile": self.spn_tile.value(),
            "model_path": self.model_path.text(),
            "theme": self.cmb_theme.currentText(),
            "font_size": self.spn_font.value(),
            "language": self.cmb_lang.currentText()
        }


    def reset_defaults(self):
        self.chk_thumbnails.setChecked(False)
        self.chk_upscale.setChecked(False)
        self.spn_scale.setValue(4)
        self.spn_tile.setValue(128)
        self.model_path.setText("src/models/RealESRNET_x4plus.pth")

    def accept(self):
        self.modified.enabled_thumbnails = self.chk_thumbnails.isChecked()
        self.modified.enabled_upscale = self.chk_upscale.isChecked()
        self.modified.save_to_json("config/settings.json")
        super().accept()