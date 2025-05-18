from real_esrgan_plugin import RealESRGANUpscaler
# 필요 시 다른 모델도 등록

PLUGINS = {
    "real-esrgan": RealESRGANUpscaler,
    # "swinir": SwinIRUpscaler,
}

def create_upscaler(name: str, settings):
    if name not in PLUGINS:
        raise ValueError(...)
    return PLUGINS[name](settings)