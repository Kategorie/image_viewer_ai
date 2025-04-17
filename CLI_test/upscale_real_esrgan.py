"""
RRDBNet 기반의 Real-ESRGAN을 사용하여 이미지를 업스케일하는 CLI 스크립트입니다.
이 스크립트는 사용자가 지정한 입력 이미지와 모델 파일을 사용하여 업스케일된 이미지를 생성합니다.
정상 작동합니다.
"""

import os
import sys
import cv2
import argparse
from basicsr.archs.rrdbnet_arch import RRDBNet
from realesrgan import RealESRGANer

parser = argparse.ArgumentParser()
parser.add_argument('--input', type=str, default='./CLI_test/test_asset/cross_0.jpg', help='입력 이미지 경로')
parser.add_argument('--output', type=str, default='./CLI_test/output/output.jpg', help='출력 이미지 경로')
parser.add_argument('--model', type=str, default='./CLI_test/weights/RealESRNet_x4plus.pth', help='모델 파일 경로')
parser.add_argument('--tile', type=int, default=0, help='타일 크기 (0이면 전체 이미지 처리)')
parser.add_argument('--pre_pad', type=int, default=0, help='패딩 크기 (0이면 패딩 없음)')
parser.add_argument('--device', type=str, default='cpu', help='장치 (cpu 또는 cuda)')
parser.add_argument('--scale', type=int, default=4, help='업스케일 배율 (기본값: 4)')

args = parser.parse_args()

if not os.path.exists(args.input):
    print(f"[!] 입력 이미지가 존재하지 않습니다: {args.input}")
    sys.exit(1)

if not os.path.exists(args.model):
    print(f"[!] 모델 파일이 존재하지 않습니다: {args.model}")
    sys.exit(1)

img = cv2.imread(args.input, cv2.IMREAD_COLOR)
if img is None:
    print(f"[!] 이미지를 불러올 수 없습니다 (경로 오류 또는 형식 문제): {args.input}")
    sys.exit(1)

model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64,
                num_block=23, num_grow_ch=32, scale=4)

upscaler = RealESRGANer(
    scale=4,
    model_path=args.model,
    model=model,
    tile=0,
    pre_pad=0,
    half=False
)

try:
    output, _ = upscaler.enhance(img)
    cv2.imwrite(args.output, output)
    print(f"[✓] 업스케일 완료: {args.output}")
except Exception as e:
    print(f"[!] 업스케일 실패: {e}")
    sys.exit(1)
