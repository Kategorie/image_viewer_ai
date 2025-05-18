from base_upscaler import BaseUpscaler
from basicsr.archs.rrdbnet_arch import RRDBNet
from realesrgan import RealESRGANer
from PIL import Image
import numpy as np

class RealESRGANUpscaler(BaseUpscaler):
    def __init__(self, settings):
        self.model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64,
                             num_block=23, num_grow_ch=32, scale=settings.scale)
        self.upscaler = RealESRGANer(
            scale=settings.scale,
            model_path=settings.model_path,
            model=self.model,
            tile=settings.tile,
            tile_pad=4,
            pre_pad=0,
            half=settings.half
        )

    def upscale(self, image: Image.Image) -> Image.Image:
        img_np = np.array(image)
        result_np, _ = self.upscaler.enhance(img_np, outscale=1)
        return Image.fromarray(result_np)