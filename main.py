"""Launch PrsfMenuForge on Windows using Python 3.11+ and PySide6."""
from __future__ import annotations
import sys


def main() -> int:
    if sys.platform != 'win32':
        print('PrsfMenuForge requires Windows 10/11; editing system menus is unavailable on this OS.')
        return 2
    try:
        from PySide6.QtWidgets import QApplication
        from app.ui import MainWindow, window_icon
    except ImportError:
        print('Missing PySide6. Run install.bat, or: python -m pip install -r requirements.txt')
        return 3
    app = QApplication(sys.argv)
    app.setApplicationName('PrsfMenuForge')
    app.setApplicationDisplayName('PrsfMenuForge')
    app.setWindowIcon(window_icon())
    app.setStyle('Fusion')
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())
