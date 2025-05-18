from .base_upscaler import BaseUpscaler
from basicsr.archs.rrdbnet_arch import RRDBNet
from realesrgan import RealESRGANer
from PIL import Image
import numpy as np

class RealESRGANUpscaler(BaseUpscaler):
    def __init__(self, settings):
        model = RRDBNet(
            num_in_ch=3,
            num_out_ch=3,
            num_feat=64,
            num_block=23,
            num_grow_ch=32,
            scale=4  # ⚠️ 고정: 모델 학습 스케일과 일치
        )

        self.upscaler = RealESRGANer(
            model_path=settings.model_path,
            model=model,
            scale=4,  # ⚠️ 고정
            tile=settings.tile,
            tile_pad=settings.tile_pad,
            half=settings.half
        )

        self.scale_factor = settings.scale_factor  # 💡 output 배율 조정용

    def upscale(self, image: Image.Image) -> Image.Image:
        img_np = np.array(image)
        result_np, _ = self.upscaler.enhance(img_np, outscale=self.scale_factor)  # ✅ 적용
        return Image.fromarray(result_np)