from abc import ABC, abstractmethod

class BaseUpscaler(ABC):
    @abstractmethod
    def upscale(self, image_path: str) -> str:
        """
        이미지를 업스케일링한 후 저장된 파일 경로를 반환합니다.
        """
        pass