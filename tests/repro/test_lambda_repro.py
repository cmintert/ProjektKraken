from PySide6.QtCore import Signal, QObject
import pytest


class Signaller(QObject):
    triggered = Signal(bool)


def test_lambda_connection():
    s = Signaller()

    # This lambda accepts no arguments - Python lambda signature check is disabled in PySide?
    callback = lambda: print("called")

    # Connecting signal with 1 arg to lambda with 0 args
    s.triggered.connect(callback)

    # Emitting
    try:
        s.triggered.emit(True)
    except TypeError as e:
        print(f"Caught expected TypeError: {e}")
        return

    # If we get here, PySide/Qt might be handling it intelligently?
    print("No TypeError caught")


if __name__ == "__main__":
    test_lambda_connection()
