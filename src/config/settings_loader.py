import os
import json
from dataclasses import dataclass, fields

DEFAULT_SETTINGS_PATH = os.path.join(os.path.dirname(__file__), "settings.json")

@dataclass
class AppSettings:
    fit_to_window: bool = True
    scale_factor: float = 1.0
    tile: int = 512
    tile_pad: int = 12
    scale: float = 4.0
    half: bool = False
    enabled_thumbnails: bool = True
    enabled_upscale: bool = False
    page_mode: str = "single"
    model_path: str = "src/models/RealESRNET_x4plus.pth"
    sequential_upscale: bool = False

    def __post_init__(self):
        self._on_change_callback = None

    @classmethod
    def load_from_json(cls, path=DEFAULT_SETTINGS_PATH):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return cls()

        return cls(**{f.name: data.get(f.name, getattr(cls(), f.name)) for f in fields(cls)})

    def get(self, key, default=None):
        return getattr(self, key, default)

    def set(self, key, value):
        setattr(self, key, value)

    def save_to_json(self, path=DEFAULT_SETTINGS_PATH):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        data_to_save = {field.name: getattr(self, field.name) for field in fields(self)}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data_to_save, f, indent=4, ensure_ascii=False)

        if self._on_change_callback:
            self._on_change_callback()

    def set_on_change_callback(self, callback):
        self._on_change_callback = callback