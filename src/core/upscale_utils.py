
def upscale_image(image_path: str) -> str:
    import shutil
    # 실제로는 AI 모델을 적용해야 함.
    # 여기서는 간단히 복사만
    result_path = image_path.replace('.', '_upscaled.')
    shutil.copy(image_path, result_path)
    return result_path
