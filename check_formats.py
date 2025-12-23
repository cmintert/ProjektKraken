import sys

from PySide6.QtGui import QImageReader
from PySide6.QtWidgets import QApplication

app = QApplication(sys.argv)
formats = [f.data().decode("utf-8") for f in QImageReader.supportedImageFormats()]
print(f"Supported formats: {formats}")
print(f"webp supported: {'webp' in formats}")
