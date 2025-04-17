import os
import json

CONFIG_PATH = "config/viewer_config.json"
DEFAULT_CONFIG = {
    "fit_to_window": True,
    "scale_factor": 1.0,
    "enable_thumbnails": True,
    "tile": 128,
    "scale": 4,
    "model_path": "src/models/RealESRNET_x4plus.pth",
    "half": False
}

def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG

def save_config(config):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)