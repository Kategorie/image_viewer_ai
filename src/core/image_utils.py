import os
import hashlib
import zipfile
import tempfile

def get_cache_path(img_path):
    hashed = hashlib.md5(img_path.encode()).hexdigest()
    filename = f"{hashed}.png"
    return os.path.join("src/cache", filename)

def is_image_file(filename):
    return filename.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".gif"))

def extract_archive(archive_path, image_extensions=None):
    """
    압축 파일을 임시 디렉토리에 해제하고, 이미지 파일 경로 리스트 반환

    Args:
        archive_path (str): ZIP 또는 CBZ 파일 경로
        image_extensions (set[str], optional): 허용할 이미지 확장자 (예: {'.png', '.jpg'})

    Returns:
        list[str]: 이미지 파일 경로 리스트
    """
    if image_extensions is None:
        image_extensions = {".png", ".jpg", ".jpeg", ".bmp", ".gif"}

    ext = os.path.splitext(archive_path)[1].lower()
    temp_dir = tempfile.mkdtemp(prefix="viewer_extract_")

    if ext not in [".zip", ".cbz"]:
        raise ValueError(f"지원하지 않는 압축 형식: {ext}")

    try:
        with zipfile.ZipFile(archive_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
    except Exception as e:
        raise RuntimeError(f"압축 해제 실패: {e}")

    image_list = sorted([
        os.path.join(temp_dir, f)
        for f in os.listdir(temp_dir)
        if os.path.splitext(f)[1].lower() in image_extensions
    ])

    return image_list

def get_file_extension(path):
    return os.path.splitext(path)[1].lower()