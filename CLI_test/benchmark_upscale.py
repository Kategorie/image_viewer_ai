"""
모델을 반복적으로 적용하여 성능을 비교하는 스크립트입니다.
다만 테스트용이라 현재 RRDBNet 모델만 사용하고 있습니다.
추후 다른 모델도 추가할 예정입니다.
"""

import os
import cv2
from basicsr.archs.rrdbnet_arch import RRDBNet
from realesrgan import RealESRGANer

# 경로 설정
input_path = './CLI_test/test_asset/cross.jpg'
model_dir = './CLI_test/weights'
output_dir = './CLI_test/benchmark_output'
os.makedirs(output_dir, exist_ok=True)

# 입력 이미지 확인
if not os.path.exists(input_path):
    print(f"[!] 입력 이미지가 존재하지 않습니다: {input_path}")
    exit(1)

img = cv2.imread(input_path, cv2.IMREAD_COLOR)
if img is None:
    print(f"[!] 이미지를 불러올 수 없습니다: {input_path}")
    exit(1)

# 모델 반복 적용
for filename in os.listdir(model_dir):
    if filename.endswith('.pth'):
        model_path = os.path.join(model_dir, filename)
        model_name = os.path.splitext(filename)[0]
        print(f"[→] 모델 적용 중: {model_name}")

        model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64,
                        num_block=23, num_grow_ch=32, scale=4)

        upscaler = RealESRGANer(
            scale=4,
            model_path=model_path,
            model=model,
            tile=0,
            pre_pad=0,
            half=False
        )

        try:
            output, _ = upscaler.enhance(img)
            save_path = os.path.join(output_dir, f'{model_name}.jpg')
            cv2.imwrite(save_path, output)
            print(f"[✓] 저장 완료 → {save_path}\n")
        except Exception as e:
            print(f"[!] {model_name} 처리 실패: {e}\n")
