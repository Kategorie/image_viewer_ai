from plugins.plugin_loader import create_upscaler

def upscale_image(image_path: str, model_name="real-esrgan") -> str:
    upscaler = create_upscaler(model_name)
    return upscaler.upscale(image_path)