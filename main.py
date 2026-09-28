"""Mühür Kontrol masaüstü uygulamasının giriş noktası."""
import multiprocessing
import sys


def main() -> int:
    from PySide6.QtWidgets import QApplication
    from app.gui.main_window import MainWindow
    from app.utils.logger import configure_logging

    configure_logging()
    application = QApplication(sys.argv)
    application.setApplicationName("Mühür Kontrol")
    application.setOrganizationName("LocalStampChecker")
    window = MainWindow()
    window.show()
    return application.exec()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    sys.exit(main())
