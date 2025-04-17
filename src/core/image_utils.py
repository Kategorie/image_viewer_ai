import hashlib
import os

def get_cache_path(img_path):
    hashed = hashlib.md5(img_path.encode()).hexdigest()
    filename = f"{hashed}.png"
    return os.path.join("src/cache", filename)

def is_image_file(filename):
    return filename.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".gif"))
