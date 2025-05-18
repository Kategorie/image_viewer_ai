import sys
from PySide6.QtWidgets import QApplication
from ui.viewer_window import ImageViewer

def main():
    app = QApplication(sys.argv)
    viewer = ImageViewer()
    viewer.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()