# main.py
# Entry point: connects GestureEngine (logic) with MainWindow (UI).

import sys
from PyQt5.QtWidgets import QApplication
from gesture_engine import GestureEngine
from ui_layer import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    engine = GestureEngine()

    window = MainWindow(engine=engine)
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
