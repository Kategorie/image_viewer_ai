import sys
from PySide6.QtWidgets import QApplication
from ui.image_viewer_ui import ImageViewer

def main():
    app = QApplication(sys.argv)
    viewer = ImageViewer()
    viewer.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()