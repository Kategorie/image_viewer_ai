import os
from config.settings_loader import AppSettings

def test_settings_load_and_save(tmp_path):
    test_file = tmp_path / "settings.json"
    settings = AppSettings()
    settings.scale_factor = 2.5
    settings.save_to_json(str(test_file))

    loaded = AppSettings.load_from_json(str(test_file))
    assert loaded.scale_factor == 2.5