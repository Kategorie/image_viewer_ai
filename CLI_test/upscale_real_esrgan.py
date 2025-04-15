import os
import argparse
import torch
from PIL import Image
import numpy as np
from torchvision.transforms.functional import to_tensor, to_pil_image

# Real-ESRGAN 관련 라이브러리 불러오기 (사전 설치 필요)
from basicsr.archs.rrdbnet_arch import RRDBNet
from realesrgan import RealESRGANer

def load_image(image_path):
    return Image.open(image_path).convert("RGB")

def save_image(image_tensor, output_path):
    image = to_pil_image(image_tensor.squeeze(0).cpu().clamp(0, 1))
    image.save(output_path)

def build_model(scale, model_path, device):
    # 기본 Real-ESRGAN x4 모델 구조
    model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, 
                    num_block=23, num_grow_ch=32, scale=scale)

    upsampler = RealESRGANer(
        scale=scale,
        model_path=model_path,
        model=model,
        tile=0,  # 전체 이미지 한번에 처리 (tile 방식으로도 가능)
        tile_pad=10,
        pre_pad=0,
        half=False,
        device=device
    )
    return upsampler

def upscale_image(input_path, output_path, model_path, scale, device):
    img = load_image(input_path)
    img_np = np.array(img)

    upsampler = build_model(scale, model_path, device)
    output, _ = upsampler.enhance(img_np, outscale=scale)

    Image.fromarray(output).save(output_path)
    print(f"[✓] Saved upscaled image to: {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Real-ESRGAN Upscaler")
    parser.add_argument("--input", type=str, required=True, help="Input image path")
    parser.add_argument("--output", type=str, required=True, help="Output image path")
    parser.add_argument("--model", type=str, required=True, help="Path to .pth model file")
    parser.add_argument("--scale", type=int, default=4, help="Upscaling factor")
    parser.add_argument("--device", type=str, choices=["cpu", "cuda"], default="cpu")
    args = parser.parse_args()

    upscale_image(
        input_path=args.input,
        output_path=args.output,
        model_path=args.model,
        scale=args.scale,
        device=torch.device(args.device)
    )
