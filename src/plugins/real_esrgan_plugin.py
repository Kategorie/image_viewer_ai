from .base_upscaler import BaseUpscaler
import shutil  # 실제로는 모델 호출로 교체

class RealESRGANUpscaler(BaseUpscaler):
    def upscale(self, image_path: str) -> str:
        # 실제 모델로 대체 필요
        result_path = image_path.replace('.', '_real_esrgan.')
        shutil.copy(image_path, result_path)
        return result_path