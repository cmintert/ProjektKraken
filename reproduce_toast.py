import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton
from PySide6.QtCore import Qt, QPoint
from src.gui.widgets.toast_notification import ToastNotification


class TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Toast Test")
        self.resize(800, 600)

        btn = QPushButton("Show Toast", self)
        btn.clicked.connect(self.show_toast)
        btn.resize(100, 50)
        btn.move(350, 275)

    def show_toast(self):
        toast = ToastNotification("Test Notification", parent=self)

        # Current Logic (approximate implementation of what I want to test)
        parent_geo = self.geometry()
        # parent_geo is global if window is shown? No, geometry() is relative to parent if widget,
        # but QMainWindow has no parent usually.

        # To get global geometry reliable:
        # parent_geo = self.frameGeometry()

        # Calculation for center:
        # center = parent_geo.center()
        # x = center.x() - toast.width() // 2
        # y = center.y() - toast.height() // 2

        # Let's try to implement this logic inside the reproduction script to see if it works
        # then I will move it to the class.

        # Using the existing method to see where it goes first?
        # toast.show_at_bottom_right()

        # Proposed new logic:
        screen_geo = self.screen().availableGeometry()
        parent_geo = self.geometry()

        # If parent is a window, geometry() is usually global screen coordinates?
        # Let's verify.
        print(f"Parent Geometry: {parent_geo}")

        # Center logic
        x = parent_geo.x() + (parent_geo.width() - toast.width()) // 2
        y = parent_geo.y() + (parent_geo.height() - toast.height()) // 2

        toast.move(x, y)
        toast.show()
        toast.raise_()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    sys.exit(app.exec())
