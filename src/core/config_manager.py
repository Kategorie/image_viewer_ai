import json
import os

DEFAULT_SETTINGS_PATH = "config/settings.json"

class ConfigManager:
    def __init__(self):
        self.config = self.load_config()

    def load_config(self):
        if os.path.exists(DEFAULT_SETTINGS_PATH):
            with open(DEFAULT_SETTINGS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        else:
            return self.load_default()

    def load_default(self):
        with open(DEFAULT_SETTINGS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    def save(self):
        with open(DEFAULT_SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=4, ensure_ascii=False)

    def reset_to_default(self):
        self.config = self.load_default()
        self.save()

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value

    def get_all(self):
        return self.config

    def update(self, values: dict):
        self.config.update(values)