# 테스트 실행 코드

python upscale_real_esrgan.py \
  --input cross.jpg \
  --output cross_upscaled.jpg \
  --model weights/RealESRGAN_x4plus.pth \
  --scale 4 \
  --device cpu