# ui_layer.py
# ─────────────────────────────────────────────────────────────
# JARVIS-style HUD UI Layer for Sasta Tony Stark
# Built with PyQt5 + QPainter. Reads state from GestureEngine.
# ─────────────────────────────────────────────────────────────

import sys
import math
import time
import cv2
import numpy as np

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QSizePolicy, QFrame, QPushButton,
    QSlider, QCheckBox, QComboBox
)
from PyQt5.QtCore import (
    Qt, QTimer, QThread, pyqtSignal, QPropertyAnimation,
    QEasingCurve, QRectF, QPointF, QRect, pyqtProperty
)
from PyQt5.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QFontMetrics,
    QLinearGradient, QRadialGradient, QImage, QPixmap,
    QPainterPath, QConicalGradient
)
from settings_manager import save_settings

# ── Palette ───────────────────────────────────────────────────
C_BG         = QColor(8, 8, 12)
C_PANEL      = QColor(12, 14, 22, 200)
C_CYAN       = QColor(0, 247, 255)
C_CYAN_DIM   = QColor(0, 180, 200, 80)
C_PURPLE     = QColor(106, 0, 255)
C_PURPLE_DIM = QColor(80, 0, 200, 80)
C_WHITE      = QColor(220, 235, 255)
C_GOLD       = QColor(255, 210, 0)
C_GOLD_DIM   = QColor(200, 160, 0, 80)
C_RED        = QColor(255, 50, 80)
C_GREEN      = QColor(0, 255, 140)
C_DARK_LINE  = QColor(30, 40, 60)
C_BLUE       = QColor(0, 140, 255)

FONT_MONO    = "Courier New"
FONT_DISPLAY = "Courier New"


# ── Helper drawing functions ───────────────────────────────────

def hex_path(cx, cy, r):
    path = QPainterPath()
    for i in range(6):
        angle = math.radians(60 * i - 30)
        x = cx + r * math.cos(angle)
        y = cy + r * math.sin(angle)
        if i == 0:
            path.moveTo(x, y)
        else:
            path.lineTo(x, y)
    path.closeSubpath()
    return path


def neon_pen(color: QColor, width=1.5, style=Qt.SolidLine) -> QPen:
    pen = QPen(color, width, style)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    return pen


# ── Camera worker thread ───────────────────────────────────────

class CameraWorker(QThread):
    frame_ready = pyqtSignal(object, float)   # (cv2 frame BGR, fps)

    def __init__(self, engine):
        super().__init__()
        self.engine = engine
        self._running = True
        self._fps = 30.0
        self._ptime = time.time()
        self._camera_index = int(self.engine.config.get("camera_index", 0))

    def run(self):
        cap = cv2.VideoCapture(self._camera_index)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        while self._running:
            desired_index = int(self.engine.config.get("camera_index", self._camera_index))
            if desired_index != self._camera_index:
                self._camera_index = desired_index
                cap.release()
                cap = cv2.VideoCapture(self._camera_index)
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            ret, frame = cap.read()
            if not ret:
                # Avoid a tight busy-loop when camera frames fail intermittently.
                time.sleep(0.01)
                continue
            ctime = time.time()
            delta = ctime - self._ptime
            if delta > 0.0001:
                self._fps = 0.9 * self._fps + 0.1 * (1.0 / delta)
            self._ptime = ctime

            frame = self.engine.process(frame, self._fps)

            if self.engine.exit_requested:
                self.stop()
                break

            self.frame_ready.emit(frame, self._fps)

        cap.release()
        cv2.destroyAllWindows()

    def stop(self):
        self._running = False
        self.quit()
        self.wait()


# ── Circular progress widget ───────────────────────────────────

class CircularGauge(QWidget):
    """Animated radial progress gauge."""

    def __init__(self, label="", color=C_CYAN, parent=None):
        super().__init__(parent)
        self.label = label
        self.color = color
        self._value = 0.0        # 0–1
        self._anim_value = 0.0
        self._pulse = 0.0
        self.setMinimumSize(130, 130)
        self.setMaximumSize(160, 160)
        # animation timer
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._tick)
        self._anim_timer.start(16)

    def set_value(self, v: float):
        self._value = max(0.0, min(1.0, v))

    def _tick(self):
        diff = self._value - self._anim_value
        self._anim_value += diff * 0.12
        self._pulse = (self._pulse + 0.05) % (2 * math.pi)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w // 2, h // 2
        r = min(w, h) // 2 - 12

        # background ring
        p.setPen(neon_pen(C_DARK_LINE, 6))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(cx, cy), r, r)

        # arc
        span = int(self._anim_value * 360 * 16)
        glow_alpha = int(180 + 60 * math.sin(self._pulse))
        arc_color = QColor(self.color)
        arc_color.setAlpha(glow_alpha)
        p.setPen(neon_pen(arc_color, 7))
        rect = QRectF(cx - r, cy - r, r * 2, r * 2)
        p.drawArc(rect, 90 * 16, -span)

        # glow halo
        halo = QColor(self.color)
        halo.setAlpha(25)
        p.setPen(neon_pen(halo, 18))
        p.drawArc(rect, 90 * 16, -span)

        # center dot
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor(self.color)))
        p.drawEllipse(QPointF(cx, cy), 4, 4)

        # percentage text
        pct = int(self._anim_value * 100)
        p.setPen(QPen(C_WHITE))
        font = QFont(FONT_MONO, 16, QFont.Bold)
        p.setFont(font)
        p.drawText(QRect(0, cy - 14, w, 28), Qt.AlignCenter, f"{pct}%")

        # label
        p.setPen(QPen(QColor(self.color)))
        font2 = QFont(FONT_MONO, 7)
        p.setFont(font2)
        p.drawText(QRect(0, cy + 18, w, 20), Qt.AlignCenter, self.label)
        p.end()


# ── HUD status panel ───────────────────────────────────────────

class HUDPanel(QWidget):
    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self._scan_y = 0.0
        self._boot_alpha = 0.0
        self._booted = False
        self._boot_lines = [
            "INITIALIZING JARVIS SUBSYSTEMS...",
            "LOADING HAND TRACKING MODULE... OK",
            "FACE DETECTION ENGINE... READY",
            "GESTURE CLASSIFIER... ARMED",
            "HUD OVERLAY... NOMINAL",
            "ALL SYSTEMS OPERATIONAL",
        ]
        self._boot_idx = 0
        self._boot_shown = []
        self._boot_timer = QTimer(self)
        self._boot_timer.timeout.connect(self._boot_tick)
        self._boot_timer.start(300)

        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self.update)
        self._anim_timer.start(33)

        self._t = 0.0
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def _boot_tick(self):
        if self._boot_idx < len(self._boot_lines):
            self._boot_shown.append(self._boot_lines[self._boot_idx])
            self._boot_idx += 1
        else:
            self._booted = True
            self._boot_timer.stop()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        self._t += 0.025

        # background
        p.fillRect(0, 0, w, h, C_BG)

        # subtle hex grid background
        self._draw_hex_grid(p, w, h)

        if not self._booted:
            self._draw_boot(p, w, h)
            p.end()
            return

        # scan line
        self._scan_y = (self._scan_y + 0.4) % h
        scan_grad = QLinearGradient(0, self._scan_y - 20, 0, self._scan_y + 20)
        scan_grad.setColorAt(0, QColor(0, 247, 255, 0))
        scan_grad.setColorAt(0.5, QColor(0, 247, 255, 18))
        scan_grad.setColorAt(1, QColor(0, 247, 255, 0))
        p.fillRect(0, int(self._scan_y) - 20, w, 40, scan_grad)

        # top header bar
        self._draw_header(p, w)

        # mode badge
        self._draw_mode_badge(p, w, h)

        # finger count
        self._draw_finger_dots(p, w, h)

        # gesture menu
        self._draw_gesture_menu(p, w, h)

        # quick telemetry
        self._draw_quick_stats(p, w, h)

        # status bar bottom
        self._draw_status_bar(p, w, h)

        # feedback toast
        if self.engine.feedback_text:
            self._draw_feedback(p, w, h)

        p.end()

    def _draw_hex_grid(self, p, w, h):
        cache_key = (w, h)

        if getattr(self, '_hex_cache_key', None) != cache_key:
            pix = QPixmap(w, h)
            pix.fill(Qt.transparent)

            cache_painter = QPainter(pix)
            cache_painter.setRenderHint(QPainter.Antialiasing)

            r = 28
            dx = r * math.sqrt(3)
            dy = r * 1.5

            cache_painter.setPen(neon_pen(QColor(20, 35, 55, 60), 0.5))

            col = 0
            x = 0.0
            while x < w + dx:
                y = 0.0
                while y < h + dy:
                    offset = (r * math.sqrt(3) / 2) if col % 2 else 0
                    hp = hex_path(x, y + offset, r - 2)
                    cache_painter.drawPath(hp)
                    y += dy * 2
                col += 1
                x += dx

            cache_painter.end()

            self._hex_cache = pix
            self._hex_cache_key = cache_key

        p.drawPixmap(0, 0, self._hex_cache)

    def _draw_boot(self, p, w, h):
        p.setPen(QPen(C_CYAN))
        p.setFont(QFont(FONT_MONO, 10))
        y = h // 3
        for line in self._boot_shown:
            color = C_GREEN if "OK" in line or "READY" in line or "ARMED" in line or "NOMINAL" in line or "OPERATIONAL" in line else C_CYAN
            p.setPen(QPen(color))
            p.drawText(40, y, line)
            y += 22
        # blinking cursor
        if int(time.time() * 2) % 2 == 0:
            p.setPen(QPen(C_CYAN))
            p.drawText(40, y, "█")

    def _draw_header(self, p, w):
        # top bar
        grad = QLinearGradient(0, 0, w, 0)
        grad.setColorAt(0, QColor(0, 247, 255, 0))
        grad.setColorAt(0.3, QColor(0, 247, 255, 60))
        grad.setColorAt(0.7, QColor(106, 0, 255, 60))
        grad.setColorAt(1, QColor(106, 0, 255, 0))
        p.fillRect(0, 0, w, 48, grad)
        p.setPen(neon_pen(C_CYAN, 1))
        p.drawLine(0, 48, w, 48)

        # title
        p.setPen(QPen(C_CYAN))
        p.setFont(QFont(FONT_DISPLAY, 13, QFont.Bold))
        p.drawText(20, 32, "◈  J.A.R.V.I.S  GESTURE CONTROL SYSTEM")

        # right side: time
        ts = time.strftime("%H:%M:%S")
        p.setPen(QPen(C_PURPLE))
        p.setFont(QFont(FONT_MONO, 9))
        p.drawText(w - 120, 32, ts)

    def _draw_mode_badge(self, p, w, h):
        mode = self.engine.get_mode_name()
        active = self.engine.settingFlag
        color = C_CYAN if active else C_PURPLE_DIM

        pulse = 0.5 + 0.5 * math.sin(self._t * 3)
        badge_color = QColor(color)
        badge_color.setAlpha(int(140 + 80 * pulse) if active else 80)

        # badge rect
        bx, by, bw, bh = 20, 60, 280, 52
        path = QPainterPath()
        path.addRoundedRect(QRectF(bx, by, bw, bh), 6, 6)
        fill = QColor(0, 247, 255, 18) if active else QColor(30, 30, 50, 80)
        p.fillPath(path, QBrush(fill))
        p.setPen(neon_pen(badge_color, 1.5))
        p.drawPath(path)

        # label
        p.setPen(QPen(QColor(120, 140, 160)))
        p.setFont(QFont(FONT_MONO, 7))
        p.drawText(bx + 12, by + 17, "ACTIVE MODE")

        p.setPen(QPen(C_WHITE if active else QColor(80, 100, 120)))
        p.setFont(QFont(FONT_DISPLAY, 14, QFont.Bold))
        p.drawText(bx + 12, by + 40, mode)

        # status dot
        dot_color = C_GREEN if active else C_RED
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(dot_color))
        p.drawEllipse(QPointF(bx + bw - 16, by + bh / 2), 5, 5)
        # glow
        glow = QColor(dot_color)
        glow.setAlpha(40)
        p.setBrush(QBrush(glow))
        p.drawEllipse(QPointF(bx + bw - 16, by + bh / 2), 10, 10)

    def _draw_finger_dots(self, p, w, h):
        fingers = self.engine.finger_count
        bx, by = 20, 130
        p.setPen(QPen(QColor(120, 140, 160)))
        p.setFont(QFont(FONT_MONO, 7))
        p.drawText(bx, by, "FINGERS DETECTED")

        for i in range(5):
            cx = bx + 14 + i * 32
            cy = by + 22
            lit = i < fingers
            if lit:
                glow = QColor(C_GOLD)
                glow.setAlpha(40)
                p.setPen(Qt.NoPen)
                p.setBrush(QBrush(glow))
                p.drawEllipse(QPointF(cx, cy), 14, 14)
                p.setBrush(QBrush(C_GOLD))
                p.drawEllipse(QPointF(cx, cy), 9, 9)
            else:
                p.setPen(neon_pen(C_DARK_LINE, 1.5))
                p.setBrush(Qt.NoBrush)
                p.drawEllipse(QPointF(cx, cy), 9, 9)

            p.setPen(QPen(C_WHITE if lit else QColor(60, 80, 100)))
            p.setFont(QFont(FONT_MONO, 7, QFont.Bold))
            p.drawText(cx - 4, cy + 4, str(i + 1))

    def _draw_gesture_menu(self, p, w, h):
        sel = self.engine.selected
        items = [
            (1, "G", "GESTURE CTRL",   C_CYAN),
            (2, "R", "GAME REMOTE",    C_PURPLE),
            (3, "V", "VOLUME",         C_GOLD),
            (4, "B", "BRIGHTNESS",     QColor(0, 200, 120)),
            (5, "X", "EXIT",           C_RED),
        ]
        bx, by = 20, 195
        p.setPen(QPen(QColor(120, 140, 160)))
        p.setFont(QFont(FONT_MONO, 7))
        p.drawText(bx, by, "GESTURE MAP")

        for idx, (num, key, label, color) in enumerate(items):
            iy = by + 18 + idx * 38
            active = (sel == num)
            pulse = 0.5 + 0.5 * math.sin(self._t * 4 + idx)

            # row background
            row_path = QPainterPath()
            row_path.addRoundedRect(QRectF(bx, iy - 14, 260, 30), 4, 4)
            if active:
                fill = QColor(color)
                fill.setAlpha(30)
                p.fillPath(row_path, QBrush(fill))
                p.setPen(neon_pen(QColor(color), 1))
                p.drawPath(row_path)
            else:
                p.setPen(neon_pen(C_DARK_LINE, 0.5))
                p.drawPath(row_path)

            # key badge
            p.setPen(Qt.NoPen)
            kcolor = QColor(color)
            kcolor.setAlpha(200 if active else 80)
            p.setBrush(QBrush(kcolor))
            p.drawRoundedRect(bx + 6, iy - 10, 22, 22, 3, 3)

            p.setPen(QPen(C_BG if active else C_WHITE))
            p.setFont(QFont(FONT_MONO, 9, QFont.Bold))
            p.drawText(bx + 10, iy + 6, key)

            # label
            p.setPen(QPen(C_WHITE if active else QColor(80, 100, 130)))
            p.setFont(QFont(FONT_MONO, 9, QFont.Bold if active else QFont.Normal))
            p.drawText(bx + 36, iy + 6, f"{num}  {label}")

            # active arrow
            if active:
                p.setPen(neon_pen(QColor(color), 2))
                p.drawText(bx + 240, iy + 6, "▶")

    def _draw_quick_stats(self, p, w, h):
        bx, by, bw, bh = 20, h - 205, 280, 110
        panel = QPainterPath()
        panel.addRoundedRect(QRectF(bx, by, bw, bh), 8, 8)
        p.fillPath(panel, QBrush(QColor(8, 16, 26, 180)))
        p.setPen(neon_pen(QColor(0, 180, 220, 80), 1))
        p.drawPath(panel)

        mode = self.engine.get_mode_name()
        fps = int(getattr(self.engine, "current_fps", 0))
        hands_count = len(self.engine.hands) if self.engine.hands else 0
        pinch = int(getattr(self.engine, "pinch_length", 0))
        status = "ARMED" if self.engine.settingFlag else "STANDBY"
        status_color = C_GREEN if self.engine.settingFlag else C_PURPLE

        p.setFont(QFont(FONT_MONO, 7))
        p.setPen(QPen(QColor(120, 140, 160)))
        p.drawText(bx + 12, by + 18, "REAL-TIME TELEMETRY")

        p.setFont(QFont(FONT_MONO, 8, QFont.Bold))
        p.setPen(QPen(C_CYAN))
        p.drawText(bx + 12, by + 40, f"MODE: {mode}")
        p.setPen(QPen(QColor(180, 220, 255)))
        perf_mode = getattr(self.engine, "performance_mode", "BALANCED")
        p.drawText(bx + 12, by + 62, f"FPS: {fps:02d}    HANDS: {hands_count}")
        p.drawText(bx + 12, by + 84, f"PERF: {perf_mode}")
        p.drawText(bx + 12, by + 102, f"PINCH LEN: {pinch:03d}px")

        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(status_color))
        p.drawEllipse(QPointF(bx + bw - 20, by + 18), 5, 5)
        p.setPen(QPen(status_color))
        p.setFont(QFont(FONT_MONO, 7, QFont.Bold))
        p.drawText(bx + bw - 74, by + 22, status)

    def _draw_status_bar(self, p, w, h):
        by = h - 32
        grad = QLinearGradient(0, by, w, by)
        grad.setColorAt(0, QColor(0, 247, 255, 0))
        grad.setColorAt(0.5, QColor(0, 247, 255, 40))
        grad.setColorAt(1, QColor(106, 0, 255, 0))
        p.fillRect(0, by, w, 32, grad)
        p.setPen(neon_pen(C_CYAN, 0.5))
        p.drawLine(0, by, w, by)

        status = "SYSTEM ACTIVE ◆ TRACKING HAND..." if self.engine.hands else "SYSTEM IDLE ◇ AWAITING INPUT"
        p.setPen(QPen(C_CYAN if self.engine.hands else QColor(60, 100, 120)))
        p.setFont(QFont(FONT_MONO, 8))
        p.drawText(16, h - 12, status)

        p.setPen(QPen(C_PURPLE))
        p.drawText(w - 160, h - 12, f"FPS  REAL-TIME  ◈")

    def _draw_feedback(self, p, w, h):
        text = self.engine.feedback_text
        fade = min(1.0, self.engine.feedback_timer / 0.5)
        alpha = int(230 * fade)

        fm = QFontMetrics(QFont(FONT_MONO, 11, QFont.Bold))
        tw = fm.horizontalAdvance(text) + 40
        bx = (w - tw) // 2
        by = h - 80

        path = QPainterPath()
        path.addRoundedRect(QRectF(bx, by, tw, 36), 8, 8)
        fill = QColor(0, 247, 255, int(25 * fade))
        p.fillPath(path, fill)
        border = QColor(C_CYAN)
        border.setAlpha(alpha)
        p.setPen(neon_pen(border, 1.5))
        p.drawPath(path)

        tc = QColor(C_WHITE)
        tc.setAlpha(alpha)
        p.setPen(QPen(tc))
        p.setFont(QFont(FONT_MONO, 11, QFont.Bold))
        p.drawText(QRect(bx, by, tw, 36), Qt.AlignCenter, text)


# ── Camera display widget ──────────────────────────────────────

class CameraView(QWidget):
    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self._pixmap = None
        self._t = 0.0
        self._corner_r = 18  # corner radius for neon frame
        self.setMinimumSize(640, 400)
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._tick)
        self._anim_timer.start(16)

    def update_frame(self, cv_frame, fps):
        self._fps = fps
        rgb = cv2.cvtColor(cv_frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
        self._pixmap = QPixmap.fromImage(qimg)
        self.update()

    def _tick(self):
        self._t += 0.03
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        # dark fill
        p.fillRect(0, 0, w, h, C_BG)

        # camera feed
        if self._pixmap:
            scaled = self._pixmap.scaled(w, h, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            x = (w - scaled.width()) // 2
            y = (h - scaled.height()) // 2

            # clip to rounded rect
            clip = QPainterPath()
            clip.addRoundedRect(QRectF(0, 0, w, h), 10, 10)
            p.setClipPath(clip)
            p.drawPixmap(x, y, scaled)
            p.setClipping(False)

        # neon corner brackets
        pulse = 0.5 + 0.5 * math.sin(self._t * 2)
        alpha = int(180 + 60 * pulse)
        bcolor = QColor(C_CYAN)
        bcolor.setAlpha(alpha)
        glow = QColor(C_CYAN)
        glow.setAlpha(40)

        bl = 36  # bracket length
        bt = 3   # bracket thickness
        m = 6    # margin

        def bracket(bx, by, flipx, flipy):
            sx = 1 if not flipx else -1
            sy = 1 if not flipy else -1
            # glow
            p.setPen(neon_pen(glow, 8))
            p.drawLine(bx, by, bx + sx * bl, by)
            p.drawLine(bx, by, bx, by + sy * bl)
            # sharp
            p.setPen(neon_pen(bcolor, bt))
            p.drawLine(bx, by, bx + sx * bl, by)
            p.drawLine(bx, by, bx, by + sy * bl)

        bracket(m, m, False, False)
        bracket(w - m, m, True, False)
        bracket(m, h - m, False, True)
        bracket(w - m, h - m, True, True)

        # crosshair center
        cx, cy = w // 2, h // 2
        cr = 30
        ccolor = QColor(C_PURPLE)
        ccolor.setAlpha(int(60 + 40 * pulse))
        p.setPen(neon_pen(ccolor, 1, Qt.DashLine))
        p.drawLine(cx - cr, cy, cx + cr, cy)
        p.drawLine(cx, cy - cr, cx, cy + cr)
        p.setPen(neon_pen(ccolor, 1))
        p.drawEllipse(QPointF(cx, cy), 6, 6)

        # rule-of-thirds tactical grid
        grid_pen = QColor(0, 247, 255, 26)
        p.setPen(neon_pen(grid_pen, 1, Qt.DotLine))
        p.drawLine(w // 3, 0, w // 3, h)
        p.drawLine((2 * w) // 3, 0, (2 * w) // 3, h)
        p.drawLine(0, h // 3, w, h // 3)
        p.drawLine(0, (2 * h) // 3, w, (2 * h) // 3)

        # FPS badge (top right inside feed)
        if hasattr(self, '_fps'):
            p.setPen(QPen(C_CYAN))
            p.setFont(QFont(FONT_MONO, 8, QFont.Bold))
            fps_text = f"FPS {int(self._fps)}"
            p.drawText(w - 75, 22, fps_text)

        # top-left vision status
        vision = "VISION LOCKED" if self.engine.hands else "SEARCHING FOR HAND"
        p.setPen(QPen(C_GREEN if self.engine.hands else C_RED))
        p.setFont(QFont(FONT_MONO, 8, QFont.Bold))
        p.drawText(14, 22, vision)

        # scanning line sweep
        sweep_y = int(((self._t * 40) % (h + 40)) - 20)
        sweep_grad = QLinearGradient(0, sweep_y - 15, 0, sweep_y + 15)
        sweep_grad.setColorAt(0, QColor(0, 247, 255, 0))
        sweep_grad.setColorAt(0.5, QColor(0, 247, 255, 22))
        sweep_grad.setColorAt(1, QColor(0, 247, 255, 0))
        p.fillRect(0, sweep_y - 15, w, 30, sweep_grad)

        # bottom info strip
        active_mode = self.engine.get_mode_name()
        strip_h = 34
        strip_grad = QLinearGradient(0, h - strip_h, 0, h)
        strip_grad.setColorAt(0, QColor(0, 0, 0, 0))
        strip_grad.setColorAt(1, QColor(0, 0, 0, 160))
        p.fillRect(0, h - strip_h, w, strip_h, strip_grad)

        p.setPen(QPen(C_CYAN if self.engine.settingFlag else C_PURPLE_DIM))
        p.setFont(QFont(FONT_MONO, 9, QFont.Bold))
        p.drawText(12, h - 10, f"◈  {active_mode}")

        p.setPen(QPen(QColor(100, 130, 180)))
        p.setFont(QFont(FONT_MONO, 8))
        p.drawText(w - 160, h - 10, "SASTA TONY STARK  v1.0")

        p.end()


# ── Gauge panel  ───────────────────────────────────────────────

class GaugePanel(QWidget):
    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self._vol_gauge  = CircularGauge("VOLUME",     C_CYAN,           self)
        self._br_gauge   = CircularGauge("BRIGHTNESS", QColor(0,200,120), self)
        self._t = 0.0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(14)

        lbl = QLabel("◈ SYSTEM GAUGES")
        lbl.setStyleSheet(f"color: rgb(0,180,200); font-family:{FONT_MONO}; font-size:8pt;")
        layout.addWidget(lbl)
        layout.addWidget(self._vol_gauge,  alignment=Qt.AlignHCenter)
        layout.addWidget(self._br_gauge,   alignment=Qt.AlignHCenter)
        layout.addStretch()

        self._update_timer = QTimer(self)
        self._update_timer.timeout.connect(self._sync)
        self._update_timer.start(50)

        self.setMaximumWidth(180)
        self.setStyleSheet("background: transparent;")

    def _sync(self):
        self._vol_gauge.set_value(self.engine.volume_level)
        self._br_gauge.set_value(self.engine.brightness_level)


class SettingsDrawer(QFrame):
    def __init__(self, engine, on_apply, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.on_apply = on_apply
        self.setFixedWidth(320)
        self.setStyleSheet(
            "QFrame { background: rgba(7, 16, 24, 240); border-left: 1px solid rgba(0,247,255,90); }"
            "QLabel { color: rgb(200,225,255); font-family: Courier New; font-size: 9pt; }"
            "QPushButton { background: rgba(0,120,140,180); color: white; border: 1px solid rgba(0,247,255,120);"
            "  border-radius: 6px; padding: 7px; font-family: Courier New; font-weight: bold; }"
            "QPushButton:hover { background: rgba(0,160,180,220); }"
            "QSlider::groove:horizontal { height: 6px; background: rgba(70,90,120,100); border-radius: 3px; }"
            "QSlider::handle:horizontal { background: rgb(0,247,255); width: 12px; margin: -4px 0; border-radius: 6px; }"
            "QComboBox, QCheckBox { color: rgb(220,240,255); font-family: Courier New; font-size: 9pt; }"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        title = QLabel("SETTINGS / CALIBRATION")
        title.setStyleSheet("font-size: 10pt; font-weight: bold; color: rgb(0,247,255);")
        root.addWidget(title)

        self.cam_combo = QComboBox()
        for i in range(4):
            self.cam_combo.addItem(f"Camera {i}", i)
        self.cam_combo.setCurrentIndex(int(self.engine.config.get("camera_index", 0)))
        root.addWidget(QLabel("Camera Index"))
        root.addWidget(self.cam_combo)

        self.theme_toggle = QCheckBox("Light Theme")
        self.theme_toggle.setChecked(self.engine.config.get("theme", "dark") == "light")
        root.addWidget(self.theme_toggle)

        self.menu_hold = self._add_slider(root, "Menu Hold (x0.1s)", 10, 40, int(self.engine.config.get("menu_hold_seconds", 2.0) * 10))
        self.mode_hold = self._add_slider(root, "Mode Hold (x0.1s)", 10, 40, int(self.engine.config.get("mode_hold_seconds", 2.0) * 10))
        self.gesture_interval = self._add_slider(root, "Gesture Interval (x0.1s)", 2, 30, int(self.engine.config.get("gesture_interval_seconds", 1.2) * 10))
        self.game_interval = self._add_slider(root, "Game Interval (x0.1s)", 1, 20, int(self.engine.config.get("game_interval_seconds", 0.5) * 10))
        self.left_swipe = self._add_slider(root, "Swipe Left Threshold (negative)", -120, -10, int(self.engine.config.get("swipe_left_threshold", -60)))
        self.right_swipe = self._add_slider(root, "Swipe Right Threshold", 10, 120, int(self.engine.config.get("swipe_right_threshold", 50)))
        self.pinch_min = self._add_slider(root, "Pinch Minimize Threshold", 6, 45, int(self.engine.config.get("pinch_minimize_threshold", 16)))
        self.pinch_close = self._add_slider(root, "Pinch Close Threshold", 6, 45, int(self.engine.config.get("pinch_close_threshold", 18)))
        self.smooth_alpha = self._add_slider(root, "Pinch Smoothing (x0.01)", 5, 95, int(self.engine.config.get("pinch_smoothing_alpha", 0.3) * 100))

        apply_btn = QPushButton("Apply + Save")
        apply_btn.clicked.connect(self._apply_save)
        root.addWidget(apply_btn)
        root.addStretch()

    def _add_slider(self, root, label, minv, maxv, value):
        root.addWidget(QLabel(label))
        sl = QSlider(Qt.Horizontal)
        sl.setMinimum(minv)
        sl.setMaximum(maxv)
        corrected = max(minv, min(maxv, value))
        sl.setValue(corrected)

        if corrected != value:
            sl.setToolTip(f"Adjusted invalid config value {value} → {corrected}")
        root.addWidget(sl)
        return sl

    def _collect(self):
        return {
            "camera_index": int(self.cam_combo.currentData()),
            "theme": "light" if self.theme_toggle.isChecked() else "dark",
            "menu_hold_seconds": self.menu_hold.value() / 10.0,
            "mode_hold_seconds": self.mode_hold.value() / 10.0,
            "gesture_interval_seconds": self.gesture_interval.value() / 10.0,
            "game_interval_seconds": self.game_interval.value() / 10.0,
            "swipe_left_threshold": self.left_swipe.value(),
            "swipe_right_threshold": self.right_swipe.value(),
            "pinch_minimize_threshold": self.pinch_min.value(),
            "pinch_close_threshold": self.pinch_close.value(),
            "pinch_smoothing_alpha": self.smooth_alpha.value() / 100.0,
        }

    def _apply_save(self):
        cfg = self._collect()
        self.on_apply(cfg)
        save_settings(cfg)


# ── Main HUD window ────────────────────────────────────────────

class HUDWindow(QMainWindow):
    def __init__(self, engine):
        super().__init__()
        self.engine = engine
        self.setWindowTitle("J.A.R.V.I.S — Sasta Tony Stark")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setStyleSheet("background: #08080c;")
        self.resize(1280, 760)
        self._show_help = False
        self._is_fullscreen = False
        self._show_settings = False

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # LEFT: HUD panel
        self._hud = HUDPanel(engine)
        self._hud.setFixedWidth(320)
        root.addWidget(self._hud)

        # CENTER: Camera
        self._cam_view = CameraView(engine)
        root.addWidget(self._cam_view, stretch=1)

        # RIGHT: Gauges
        self._gauges = GaugePanel(engine)
        root.addWidget(self._gauges)

        # SETTINGS DRAWER
        self._settings_drawer = SettingsDrawer(engine, self._apply_settings, self)
        self._settings_drawer.setVisible(False)
        root.addWidget(self._settings_drawer)

        # border overlay (painted on root)
        self._border_color = C_CYAN

        # drag support
        self._drag_pos = None
        self._apply_theme(self.engine.config.get("theme", "dark"))

    def feed_frame(self, cv_frame, fps):
        self.engine.set_current_fps(fps)
        self._cam_view.update_frame(cv_frame, fps)

    # window drag
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_pos = e.globalPos() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if e.buttons() == Qt.LeftButton and self._drag_pos:
            self.move(e.globalPos() - self._drag_pos)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.close()
        elif e.key() == Qt.Key_H:
            self._show_help = not self._show_help
            self.update()
        elif e.key() == Qt.Key_F11:
            if self._is_fullscreen:
                self.showNormal()
            else:
                self.showFullScreen()
            self._is_fullscreen = not self._is_fullscreen
        elif e.key() == Qt.Key_M:
            self.showMinimized()
        elif e.key() == Qt.Key_S:
            self._show_settings = not self._show_settings
            self._settings_drawer.setVisible(self._show_settings)
            self.update()

    def paintEvent(self, event):
        # outer neon border
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pulse = 0.5 + 0.5 * math.sin(time.time() * 2)
        bc = QColor(self._border_color)
        bc.setAlpha(int(100 + 80 * pulse))
        p.setPen(neon_pen(bc, 2))
        p.drawRect(1, 1, self.width() - 2, self.height() - 2)

        # quick controls banner
        p.setPen(QPen(QColor(0, 247, 255, 180)))
        p.setFont(QFont(FONT_MONO, 8))
        p.drawText(16, self.height() - 14, "H: HELP    S: SETTINGS    F11: FULLSCREEN    M: MINIMIZE    ESC: EXIT")

        if self._show_help:
            self._draw_help_overlay(p)
        p.end()

    def _draw_help_overlay(self, p: QPainter):
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, QColor(0, 0, 0, 170))

        bw, bh = min(760, w - 80), min(520, h - 80)
        bx, by = (w - bw) // 2, (h - bh) // 2

        card = QPainterPath()
        card.addRoundedRect(QRectF(bx, by, bw, bh), 12, 12)
        p.fillPath(card, QBrush(QColor(10, 16, 26, 235)))
        p.setPen(neon_pen(QColor(0, 247, 255, 180), 1.8))
        p.drawPath(card)

        p.setPen(QPen(C_CYAN))
        p.setFont(QFont(FONT_DISPLAY, 14, QFont.Bold))
        p.drawText(bx + 20, by + 36, "J.A.R.V.I.S QUICK GUIDE")

        p.setPen(QPen(QColor(170, 210, 240)))
        p.setFont(QFont(FONT_MONO, 9))
        lines = [
            "• Make a closed fist for 2s to toggle settings mode",
            "• 1 finger (2s): Gesture controller",
            "• 2 fingers (2s): Game remote",
            "• 3 fingers (2s): Volume mode (pinch)",
            "• 4 fingers (2s): Brightness mode (pinch)",
            "• 5 fingers (2s): Exit app",
            "",
            "Hotkeys:",
            "• H = toggle this help",
            "• F11 = fullscreen/windowed",
            "• M = minimize",
            "• ESC = close app",
        ]
        y = by + 74
        for line in lines:
            p.drawText(bx + 24, y, line)
            y += 28

        p.setPen(QPen(QColor(0, 247, 255, 150)))
        p.setFont(QFont(FONT_MONO, 8, QFont.Bold))
        p.drawText(bx + 24, by + bh - 18, "TIP: Keep hand centered and well-lit for best tracking.")

    def _apply_theme(self, theme_name: str):
        if theme_name == "light":
            self.setStyleSheet("background: #e8f0f6;")
            self._border_color = C_BLUE
        else:
            self.setStyleSheet("background: #08080c;")
            self._border_color = C_CYAN

    def _apply_settings(self, cfg: dict):
        self.engine.apply_settings(cfg)
        self._apply_theme(self.engine.config.get("theme", "dark"))


# ── Public API ─────────────────────────────────────────────────

def create_app(engine):
    """Create and return QApplication + HUDWindow."""
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")
    win = HUDWindow(engine)
    return app, win
