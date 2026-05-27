# main.py
# ─────────────────────────────────────────────────────────────
# Entry point: wires GestureEngine → CameraWorker → HUDWindow
# ─────────────────────────────────────────────────────────────

import sys
from PyQt5.QtWidgets import QApplication

from gesture_engine import GestureEngine
from ui_layer import create_app, CameraWorker


def main():
    try:
        engine = GestureEngine()
        app, win = create_app(engine)

        # Camera worker thread
        worker = CameraWorker(engine)
        worker.frame_ready.connect(win.feed_frame)
        worker.start()

        win.show()

        def on_close():
            worker.stop()

        app.aboutToQuit.connect(on_close)
        sys.exit(app.exec_())
    except Exception as exc:
        print(f"Startup error: {exc}")
        raise


if __name__ == "__main__":
    main()
