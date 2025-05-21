import logging
from .real_esrgan_plugin import RealESRGANUpscaler
# from .waifu2x_plugin import Waifu2xUpscaler

PLUGINS = {
    "real-esrgan": RealESRGANUpscaler,
    # "waifu2x": Waifu2xUpscaler,
}

def create_upscaler(name: str, settings):
    name = name.lower()
    if name not in PLUGINS:
        logging.error(f"지원하지 않는 업스케일러: {name}")
        raise ValueError(f"지원하지 않는 업스케일러: {name}")
    
    print(f"[DEBUG] RealESRGAN 사용 tile={settings.tile}, tile_pad={settings.tile_pad}, half={settings.half}")
    return PLUGINS[name](settings)