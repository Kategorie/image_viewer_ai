from basicsr.archs.rrdbnet_arch import RRDBNet
from realesrgan import RealESRGANer

def create_upscaler(config):
    model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64,
                    num_block=23, num_grow_ch=32, scale=4)
    return RealESRGANer(
        scale=config.get("scale", 4),
        model_path=config.get("model_path", "src/models/RealESRNET_x4plus.pth"),
        model=model,
        tile=config.get("tile", 128),
        tile_pad=4,
        pre_pad=0,
        half=config.get("half", False)
    )