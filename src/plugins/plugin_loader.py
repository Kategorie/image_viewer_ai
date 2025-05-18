from .real_esrgan_plugin import RealESRGANUpscaler
# 필요 시 다른 모델도 등록

def create_upscaler(model_name: str):
    if model_name == "real-esrgan":
        return RealESRGANUpscaler()
    else:
        raise ValueError(f"지원하지 않는 모델: {model_name}")