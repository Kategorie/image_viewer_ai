import json
from dataclasses import dataclass
from typing import Any


@dataclass
class AppSettings:
    fit_to_window: bool = True
    scale_factor: float = 1.0
    enabled_thumbnails: bool = True
    enabled_upscale: bool = False
    tile: int = 128
    scale: int = 4
    model_path: str = "src/models/RealESRNET_x4plus.pth"
    half: bool = False
    page_mode: str = "single"
    language: str = "ko"

    @staticmethod
    def load_from_json(path: str) -> "AppSettings":
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return AppSettings(**data)
        except Exception as e:
            print(f"[WARNING] Failed to load settings. Using default. Error: {e}")
            return AppSettings()
    
    def save_to_json(self, path: str):
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.__dict__, f, indent=2, ensure_ascii=False)
            print(f"[INFO] Settings saved to {path}")
        except Exception as e:
            print(f"[ERROR] Failed to save settings. Error: {e}")