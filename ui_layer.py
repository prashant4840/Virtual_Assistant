# ui_layer.py
# Futuristic Tony Stark–style HUD built with PyQt5.
# Consumes state from GestureEngine; does NOT touch gesture logic.

import math
import sys
import time

import numpy as np
import cv2

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel,
    QVBoxLayout, QHBoxLayout, QSizePolicy, QGraphicsOpacityEffect,
)
from PyQt5.QtCore import (
    Qt, QTimer, QRect, QRectF, QPoint, QSize,
    QPropertyAnimation, QEasingCurve, pyqtSignal, QObject,
)
from PyQt5.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QFontMetrics,
    QImage, QPixmap, QLinearGradient, QRadialGradient,
    QPainterPath, QPolygonF,
)

# ── Palette ──────────────────────────────────────────────────────────────────
C_BG        = QColor(10,  10,  10)        # #0a0a0a
C_CYAN      = QColor(0,  247, 255)        # #00f7ff
C_CYAN_DIM  = QColor(0,  247, 255, 60)
C_PURPLE    = QColor(106,  0, 255)        # #6a00ff
C_PURPLE_DIM= QColor(106,  0, 255, 60)
C_GOLD      = QColor(255, 200,  50)
C_WHITE     = QColor(220, 220, 220)
C_DIM       = QColor(60,  60,  60)
C_GREEN     = QColor(50,  255, 100)
C_RED       = QColor(255,  50,  50)
C_PANEL     = QColor(15,  20,  28)

FONT_MONO = "Courier New"
FONT_HUD  = "Courier New"

MODE_NAMES = {
    0: "IDLE",
    1: "GESTURE CTRL",
    2: "GAME MODE",
    3: "VOLUME CTRL",
    4: "BRIGHTNESS",
    5: "EXIT",
}

GESTURE_ITEMS = [
    ("1", "CONTROLLER"),
    ("2", "GAME MODE"),
    ("3", "VOLUME"),
    ("4", "BRIGHTNESS"),
    ("5", "EXIT"),
]

STARTUP_LINES = [
    "LOADING AI MODULES...",
    "INITIALIZING MEDIAPIPE...",
    "CALIBRATING GESTURE ENGINE...",
    "STARTING CAMERA FEED...",
    "SYSTEM ONLINE",
]


# ── Utility drawing helpers ───────────────────────────────────────────────────

def draw_glow_text(painter: QPainter, text: str, rect: QRectF,
                   color: QColor, font: QFont,
                   align=Qt.AlignCenter, glow_layers: int = 3):
    """Draw text with a multi-layer glow halo."""
    for i in range(glow_layers, 0, -1):
        alpha = int(50 / i)
        pen_color = QColor(color.red(), color.green(), color.blue(), alpha)
        painter.setPen(QPen(pen_color))
        painter.setFont(font)
        # Slight offset enlargement for glow
        bloat = i * 2
        r = QRectF(rect.x() - bloat, rect.y() - bloat,
                   rect.width() + bloat * 2, rect.height() + bloat * 2)
        painter.drawText(r, align, text)
    # Crisp foreground text
    painter.setPen(QPen(color))
    painter.setFont(font)
    painter.drawText(rect, align, text)


def draw_neon_rect(painter: QPainter, rect: QRectF,
                   color: QColor, width: int = 1, corner_only: bool = False,
                   corner_len: int = 18, radius: int = 0):
    """Draw a neon rectangle or corner brackets."""
    if corner_only:
        pen = QPen(color, width)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
        cl = corner_len
        # TL
        painter.drawLine(int(x), int(y), int(x + cl), int(y))
        painter.drawLine(int(x), int(y), int(x), int(y + cl))
        # TR
        painter.drawLine(int(x + w), int(y), int(x + w - cl), int(y))
        painter.drawLine(int(x + w), int(y), int(x + w), int(y + cl))
        # BL
        painter.drawLine(int(x), int(y + h), int(x + cl), int(y + h))
        painter.drawLine(int(x), int(y + h), int(x), int(y + h - cl))
        # BR
        painter.drawLine(int(x + w), int(y + h), int(x + w - cl), int(y + h))
        painter.drawLine(int(x + w), int(y + h), int(x + w), int(y + h - cl))
    else:
        pen = QPen(color, width)
        painter.setPen(pen)
        if radius > 0:
            painter.drawRoundedRect(rect, radius, radius)
        else:
            painter.drawRect(rect)


def draw_circle_progress(painter: QPainter, cx: int, cy: int, r: int,
                          value: float, color: QColor,
                          bg_color: QColor = C_DIM, thickness: int = 8,
                          label: str = ""):
    """Draw an animated circular progress arc (value 0–100)."""
    painter.setRenderHint(QPainter.Antialiasing)
    rect = QRectF(cx - r, cy - r, r * 2, r * 2)

    # Background track
    pen = QPen(bg_color, thickness)
    pen.setCapStyle(Qt.FlatCap)
    painter.setPen(pen)
    painter.drawArc(rect, 0, 360 * 16)

    # Glow layers
    for gl in range(3, 0, -1):
        glow_col = QColor(color.red(), color.green(), color.blue(),
                          40 * gl)
        gpen = QPen(glow_col, thickness + gl * 3)
        gpen.setCapStyle(Qt.RoundCap)
        painter.setPen(gpen)
        span = int(value / 100 * 360 * 16)
        painter.drawArc(rect, 90 * 16, -span)

    # Main arc
    pen = QPen(color, thickness)
    pen.setCapStyle(Qt.RoundCap)
    painter.setPen(pen)
    span = int(value / 100 * 360 * 16)
    painter.drawArc(rect, 90 * 16, -span)

    # Center percentage text
    font = QFont(FONT_MONO, int(r * 0.36), QFont.Bold)
    pct_text = f"{int(value)}%"
    draw_glow_text(painter, pct_text,
                   QRectF(cx - r, cy - r * 0.5, r * 2, r),
                   color, font, Qt.AlignCenter, 1)

    if label:
        lfont = QFont(FONT_MONO, max(7, int(r * 0.22)))
        draw_glow_text(painter, label,
                       QRectF(cx - r, cy + r * 0.3, r * 2, r * 0.6),
                       C_WHITE, lfont, Qt.AlignCenter, 0)


# ── Startup Widget ────────────────────────────────────────────────────────────

class StartupWidget(QWidget):
    """Full-screen animated startup sequence."""

    done = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self._phase = 0        # 0 = lines appearing, 1 = hold, 2 = fade-out
        self._line_idx = 0
        self._visible_lines: list[str] = []
        self._progress = 0.0
        self._alpha = 255
        self._tick = 0
        self._scan_x = 0

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._step)
        self._timer.start(40)  # ~25 fps

    def _step(self):
        self._tick += 1
        self._scan_x = (self._scan_x + 12) % max(self.width(), 1)

        if self._phase == 0:
            # Reveal one line every ~20 ticks
            if self._tick % 18 == 0 and self._line_idx < len(STARTUP_LINES):
                self._visible_lines.append(STARTUP_LINES[self._line_idx])
                self._line_idx += 1
            # Progress bar
            target = self._line_idx / len(STARTUP_LINES) * 100
            self._progress += (target - self._progress) * 0.12
            if self._line_idx >= len(STARTUP_LINES) and self._progress >= 98:
                self._phase = 1
                self._tick = 0

        elif self._phase == 1:
            if self._tick > 30:
                self._phase = 2
                self._tick = 0

        elif self._phase == 2:
            self._alpha = max(0, self._alpha - 12)
            if self._alpha <= 0:
                self._timer.stop()
                self.done.emit()

        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        # Background
        p.fillRect(0, 0, w, h, QColor(C_BG.red(), C_BG.green(), C_BG.blue(), self._alpha))

        # Animated grid
        grid_col = QColor(0, 247, 255, max(0, int(15 * self._alpha / 255)))
        p.setPen(QPen(grid_col, 1))
        step = 40
        for gx in range(0, w, step):
            p.drawLine(gx, 0, gx, h)
        for gy in range(0, h, step):
            p.drawLine(0, gy, w, gy)

        # Horizontal scan line
        scan_col = QColor(0, 247, 255, max(0, int(80 * self._alpha / 255)))
        p.setPen(QPen(scan_col, 2))
        sy = int(h * 0.5 + math.sin(self._tick * 0.15) * h * 0.35)
        p.drawLine(0, sy, w, sy)

        # Title
        title_font = QFont(FONT_HUD, 42, QFont.Bold)
        title_col = QColor(C_CYAN.red(), C_CYAN.green(), C_CYAN.blue(),
                           min(255, self._alpha))
        draw_glow_text(p, "SASTA TONY STARK",
                       QRectF(0, h * 0.10, w, 70),
                       title_col, title_font, Qt.AlignCenter, 4)

        sub_font = QFont(FONT_HUD, 14)
        sub_col = QColor(C_PURPLE.red(), C_PURPLE.green(), C_PURPLE.blue(),
                         min(200, self._alpha))
        draw_glow_text(p, "— GESTURE CONTROLLER —",
                       QRectF(0, h * 0.10 + 75, w, 30),
                       sub_col, sub_font, Qt.AlignCenter, 2)

        # Init lines
        line_font = QFont(FONT_MONO, 12)
        line_y = h * 0.35
        for i, line in enumerate(self._visible_lines):
            is_last = (i == len(self._visible_lines) - 1)
            col = QColor(C_GREEN.red(), C_GREEN.green(), C_GREEN.blue(),
                         min(220, self._alpha)) if is_last else \
                  QColor(C_CYAN.red(), C_CYAN.green(), C_CYAN.blue(),
                         min(160, self._alpha))
            draw_glow_text(p, f"> {line}",
                           QRectF(w * 0.3, line_y + i * 28, w * 0.4, 28),
                           col, line_font, Qt.AlignLeft, 1 if is_last else 0)

        # Progress bar
        bar_y = h * 0.78
        bar_x = w * 0.2
        bar_w = w * 0.6
        bar_h = 10
        # Track
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(C_DIM))
        p.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_h), 5, 5)
        # Fill
        filled = int(bar_w * self._progress / 100)
        if filled > 0:
            grad = QLinearGradient(bar_x, 0, bar_x + bar_w, 0)
            grad.setColorAt(0, C_PURPLE)
            grad.setColorAt(1, C_CYAN)
            p.setBrush(QBrush(grad))
            p.drawRoundedRect(QRectF(bar_x, bar_y, filled, bar_h), 5, 5)
        # Percentage label
        pct_font = QFont(FONT_MONO, 11)
        pct_col = QColor(C_WHITE.red(), C_WHITE.green(), C_WHITE.blue(),
                         min(200, self._alpha))
        draw_glow_text(p, f"{int(self._progress)}%",
                       QRectF(0, bar_y + 16, w, 22),
                       pct_col, pct_font, Qt.AlignCenter, 0)


# ── Camera View Widget ────────────────────────────────────────────────────────

class CameraView(QWidget):
    """Displays the processed camera frame with a HUD overlay (corners, scan-line)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap: QPixmap | None = None
        self._scan_y = 0
        self._tick = 0
        self.setMinimumSize(640, 480)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_frame(self, bgr_frame):
        if bgr_frame is None:
            return
        rgb = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        bytes_per_line = ch * w
        qi = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888).copy()
        self._pixmap = QPixmap.fromImage(qi)
        self.update()

    def tick(self):
        """Called each UI tick to advance scan-line animation."""
        self._tick += 1
        self._scan_y = (self._scan_y + 3) % max(self.height(), 1)
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        # Dark background
        p.fillRect(0, 0, w, h, C_BG)

        if self._pixmap:
            # Scale frame to fit, keeping aspect ratio
            scaled = self._pixmap.scaled(w, h, Qt.KeepAspectRatio,
                                          Qt.SmoothTransformation)
            ox = (w - scaled.width()) // 2
            oy = (h - scaled.height()) // 2
            p.drawPixmap(ox, oy, scaled)
            fw, fh = scaled.width(), scaled.height()
        else:
            # No-signal placeholder
            p.setPen(QPen(C_DIM, 1))
            p.setFont(QFont(FONT_MONO, 14))
            p.drawText(QRectF(0, 0, w, h), Qt.AlignCenter,
                       "AWAITING CAMERA FEED...")
            ox, oy, fw, fh = 0, 0, w, h

        # Subtle scan-line
        scan_col = QColor(0, 247, 255, 25)
        p.setPen(QPen(scan_col, 2))
        scan_abs = oy + (self._scan_y % fh)
        p.drawLine(ox, scan_abs, ox + fw, scan_abs)

        # Corner brackets
        draw_neon_rect(p, QRectF(ox, oy, fw, fh),
                       C_CYAN, width=2, corner_only=True, corner_len=22)

        # Animated corner dot pulse
        pulse = abs(math.sin(self._tick * 0.08))
        dot_col = QColor(0, 247, 255, int(180 * pulse) + 60)
        dot_r = 4
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(dot_col))
        for px, py in [(ox, oy), (ox + fw, oy), (ox, oy + fh), (ox + fw, oy + fh)]:
            p.drawEllipse(QPoint(px, py), dot_r, dot_r)


# ── HUD Panel ─────────────────────────────────────────────────────────────────

class HUDPanel(QWidget):
    """Right-side panel: mode, finger count, circular progress, gesture menu."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._state: dict = {}
        self._tick = 0
        self._prev_mode = 0
        self._mode_flash = 0      # ticks remaining when mode changed
        self._feedback = ""
        self._feedback_ticks = 0
        self._volume_display   = 50.0
        self._bright_display   = 50.0
        self.setMinimumWidth(380)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

    def update_state(self, state: dict):
        if not state:
            return
        mode = state.get("selected_mode", 0)
        if mode != self._prev_mode:
            self._mode_flash = 30
            mode_name = MODE_NAMES.get(mode, "IDLE")
            if mode == 3:
                self._feedback = "VOLUME CONTROL ACTIVE"
            elif mode == 4:
                self._feedback = "BRIGHTNESS CONTROL ACTIVE"
            elif mode == 1:
                self._feedback = "GESTURE CONTROLLER ACTIVE"
            elif mode == 2:
                self._feedback = "GAME MODE ACTIVE"
            self._feedback_ticks = 80
        self._prev_mode = mode
        self._state = state

        # Smooth level transitions
        vol  = state.get("volume_level", self._volume_display)
        bri  = state.get("brightness_level", self._bright_display)
        self._volume_display += (vol - self._volume_display) * 0.15
        self._bright_display += (bri - self._bright_display) * 0.15

    def tick(self):
        self._tick += 1
        if self._mode_flash > 0:
            self._mode_flash -= 1
        if self._feedback_ticks > 0:
            self._feedback_ticks -= 1
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        # Panel background
        p.fillRect(0, 0, w, h, C_PANEL)

        # Left border accent
        grad = QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0, C_PURPLE)
        grad.setColorAt(0.5, C_CYAN)
        grad.setColorAt(1, C_PURPLE)
        p.setPen(QPen(QBrush(grad), 2))
        p.drawLine(0, 0, 0, h)

        # ── Section: Title ──────────────────────────────────────────────────
        title_font = QFont(FONT_HUD, 13, QFont.Bold)
        draw_glow_text(p, "◈  SASTA TONY STARK  ◈",
                       QRectF(0, 12, w, 26),
                       C_CYAN, title_font, Qt.AlignCenter, 2)
        p.setPen(QPen(C_CYAN_DIM, 1))
        p.drawLine(10, 44, w - 10, 44)

        # ── Section: Status line ────────────────────────────────────────────
        fps   = self._state.get("fps", 0)
        is_active = self._state.get("is_active", False)
        status_col = C_GREEN if is_active else C_GOLD
        status_txt = "● ACTIVE" if is_active else "○ SCANNING"
        sf = QFont(FONT_MONO, 10)
        p.setFont(sf)
        p.setPen(QPen(status_col))
        p.drawText(QRectF(14, 52, w // 2, 18), Qt.AlignLeft, status_txt)
        p.setPen(QPen(C_DIM))
        p.drawText(QRectF(0, 52, w - 14, 18), Qt.AlignRight,
                   f"FPS  {fps:.0f}")

        p.setPen(QPen(C_CYAN_DIM, 1))
        p.drawLine(10, 76, w - 10, 76)

        # ── Section: Active Mode ────────────────────────────────────────────
        mode   = self._state.get("selected_mode", 0)
        s_flag = self._state.get("setting_flag", False)
        mode_name = MODE_NAMES.get(mode, "IDLE")
        if not s_flag and mode == 0:
            mode_label = "MENU CLOSED"
        elif s_flag and mode == 0:
            mode_label = "SELECT MODE"
        else:
            mode_label = mode_name

        # Flash on mode change
        if self._mode_flash > 0:
            pulse = abs(math.sin(self._mode_flash * 0.3))
            mc = QColor(int(C_CYAN.red() * pulse + C_PURPLE.red() * (1 - pulse)),
                        int(C_CYAN.green() * pulse),
                        int(C_CYAN.blue() * pulse + C_PURPLE.blue() * (1 - pulse)))
        else:
            mc = C_CYAN

        mode_font = QFont(FONT_HUD, 16, QFont.Bold)
        draw_glow_text(p, "ACTIVE MODE", QRectF(0, 84, w, 20),
                       C_DIM, QFont(FONT_MONO, 9), Qt.AlignCenter, 0)
        draw_glow_text(p, mode_label, QRectF(0, 104, w, 34),
                       mc, mode_font, Qt.AlignCenter, 3)

        # ── Fingers ─────────────────────────────────────────────────────────
        fingers = self._state.get("finger_count", 0)
        self._draw_finger_dots(p, w, 148, fingers)

        p.setPen(QPen(C_CYAN_DIM, 1))
        p.drawLine(10, 174, w - 10, 174)

        # ── Circular progress indicators ─────────────────────────────────────
        cy_vol = 250
        cy_bri = 250
        cx_vol = w // 4
        cx_bri = w * 3 // 4
        r_circ = min(w // 5, 56)

        draw_circle_progress(p, cx_vol, cy_vol, r_circ,
                             self._volume_display, C_CYAN,
                             label="VOLUME")
        draw_circle_progress(p, cx_bri, cy_bri, r_circ,
                             self._bright_display, C_PURPLE,
                             label="BRIGHT")

        p.setPen(QPen(C_CYAN_DIM, 1))
        p.drawLine(10, cy_vol + r_circ + 22, w - 10, cy_vol + r_circ + 22)

        # ── Gesture Menu ─────────────────────────────────────────────────────
        menu_top = cy_vol + r_circ + 32
        self._draw_gesture_menu(p, w, menu_top, mode, s_flag)

        # ── Feedback ticker ──────────────────────────────────────────────────
        if self._feedback_ticks > 0 and self._feedback:
            alpha = min(255, self._feedback_ticks * 5)
            fb_col = QColor(C_GOLD.red(), C_GOLD.green(), C_GOLD.blue(), alpha)
            fb_font = QFont(FONT_MONO, 10, QFont.Bold)
            draw_glow_text(p, f"⚡ {self._feedback}",
                           QRectF(0, h - 36, w, 24),
                           fb_col, fb_font, Qt.AlignCenter, 1)

    def _draw_finger_dots(self, p: QPainter, w: int, y: int, fingers: int):
        """Row of 5 dots indicating detected finger count."""
        dot_r = 8
        spacing = 28
        total = 5 * spacing
        start_x = (w - total) // 2 + spacing // 2

        label_font = QFont(FONT_MONO, 8)
        p.setFont(label_font)
        p.setPen(QPen(C_DIM))
        p.drawText(QRectF(0, y - 16, w, 16), Qt.AlignCenter, "FINGERS DETECTED")

        for i in range(5):
            cx = start_x + i * spacing
            active = (i < fingers)
            if active:
                pulse = abs(math.sin(self._tick * 0.1 + i * 0.5))
                col = QColor(0, int(220 + 35 * pulse), int(220 + 35 * pulse))
                # Glow
                glow = QColor(0, 247, 255, 40)
                p.setPen(Qt.NoPen)
                p.setBrush(QBrush(glow))
                p.drawEllipse(QPoint(cx, y + dot_r), dot_r + 4, dot_r + 4)
                p.setBrush(QBrush(col))
            else:
                p.setPen(Qt.NoPen)
                p.setBrush(QBrush(C_DIM))
            p.drawEllipse(QPoint(cx, y + dot_r), dot_r, dot_r)

            # Finger number below
            p.setPen(QPen(C_DIM if not active else C_CYAN))
            p.setFont(QFont(FONT_MONO, 7))
            p.drawText(QRectF(cx - 8, y + dot_r * 2 + 4, 16, 14),
                       Qt.AlignCenter, str(i + 1))

    def _draw_gesture_menu(self, p: QPainter, w: int, top: int,
                            active_mode: int, setting_flag: bool):
        """Gesture option list with the active item highlighted."""
        p.setFont(QFont(FONT_MONO, 9))
        draw_glow_text(p, "GESTURE MAP",
                       QRectF(0, top, w, 18),
                       C_DIM, QFont(FONT_MONO, 9), Qt.AlignCenter, 0)
        top += 22
        row_h = 30
        for idx, (num, name) in enumerate(GESTURE_ITEMS):
            mode_id = idx + 1
            is_active = (active_mode == mode_id) and setting_flag

            ry = top + idx * row_h
            rx = 16

            if is_active:
                # Highlight background
                pulse = abs(math.sin(self._tick * 0.12))
                bg_a = int(40 + 30 * pulse)
                p.setPen(Qt.NoPen)
                p.setBrush(QBrush(QColor(0, 247, 255, bg_a)))
                p.drawRoundedRect(QRectF(rx - 4, ry + 2, w - 24, row_h - 4), 4, 4)
                draw_neon_rect(p, QRectF(rx - 4, ry + 2, w - 24, row_h - 4),
                               C_CYAN, width=1)
                num_col = C_CYAN
                name_col = QColor(220, 220, 220)
            else:
                num_col = C_PURPLE
                name_col = C_DIM

            # Number badge
            p.setPen(Qt.NoPen)
            badge_col = QColor(num_col.red(), num_col.green(), num_col.blue(), 60)
            p.setBrush(QBrush(badge_col))
            p.drawEllipse(QPoint(rx + 10, ry + row_h // 2), 10, 10)

            p.setPen(QPen(num_col))
            p.setFont(QFont(FONT_MONO, 10, QFont.Bold))
            p.drawText(QRectF(rx, ry, 24, row_h), Qt.AlignCenter, num)

            p.setPen(QPen(name_col))
            p.setFont(QFont(FONT_MONO, 10))
            p.drawText(QRectF(rx + 26, ry, w - rx - 30, row_h),
                       Qt.AlignVCenter, name)


# ── Status Bar ────────────────────────────────────────────────────────────────

class StatusBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._message = "INITIALIZING..."
        self._tick = 0
        self.setFixedHeight(34)

    def set_message(self, msg: str):
        self._message = msg

    def tick(self):
        self._tick += 1
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, C_PANEL)
        p.setPen(QPen(C_CYAN_DIM, 1))
        p.drawLine(0, 0, w, 0)

        # Scrolling animated marker
        scroll_x = (self._tick * 3) % max(w, 1)
        ml = QLinearGradient(scroll_x - 60, 0, scroll_x + 60, 0)
        ml.setColorAt(0.0, QColor(0, 247, 255, 0))
        ml.setColorAt(0.5, QColor(0, 247, 255, 60))
        ml.setColorAt(1.0, QColor(0, 247, 255, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(ml))
        p.drawRect(0, 0, w, h)

        pulse = abs(math.sin(self._tick * 0.1))
        dot_col = QColor(0, 247, 255, int(150 + 105 * pulse))
        p.setPen(QPen(dot_col))
        p.setFont(QFont(FONT_MONO, 9))
        p.drawText(QRectF(10, 0, 20, h), Qt.AlignVCenter, "◈")

        p.setPen(QPen(C_CYAN))
        p.setFont(QFont(FONT_MONO, 10))
        p.drawText(QRectF(30, 0, w - 60, h), Qt.AlignVCenter,
                   self._message)

        # Right-side timestamp
        ts = time.strftime("%H:%M:%S")
        p.setPen(QPen(C_DIM))
        p.setFont(QFont(FONT_MONO, 9))
        p.drawText(QRectF(0, 0, w - 10, h), Qt.AlignVCenter | Qt.AlignRight, ts)


# ── Title Bar ─────────────────────────────────────────────────────────────────

class TitleBar(QWidget):
    """Custom frameless-window title bar with drag support."""

    close_requested = pyqtSignal()
    minimize_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(40)
        self._drag_pos = None

    def paintEvent(self, _event):
        p = QPainter(self)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, C_PANEL)

        p.setPen(QPen(C_CYAN_DIM, 1))
        p.drawLine(0, h - 1, w, h - 1)

        # Logo / title
        p.setPen(QPen(C_CYAN))
        p.setFont(QFont(FONT_HUD, 12, QFont.Bold))
        p.drawText(QRectF(14, 0, 400, h), Qt.AlignVCenter,
                   "◈  SASTA TONY STARK  —  GESTURE CONTROLLER")

        # Window buttons
        btn_r = 8
        for bx, col in [(w - 22, C_RED), (w - 46, C_GOLD)]:
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(col))
            p.drawEllipse(QPoint(bx, h // 2), btn_r, btn_r)
        p.setPen(QPen(C_WHITE))
        p.setFont(QFont(FONT_MONO, 8))
        p.drawText(QRectF(w - 30, 0, 16, h), Qt.AlignCenter, "×")
        p.drawText(QRectF(w - 54, 0, 16, h), Qt.AlignCenter, "—")

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            # Check close / minimize buttons
            w, h = self.width(), self.height()
            if abs(e.x() - (w - 22)) <= 12 and abs(e.y() - h // 2) <= 12:
                self.close_requested.emit()
                return
            if abs(e.x() - (w - 46)) <= 12 and abs(e.y() - h // 2) <= 12:
                self.minimize_requested.emit()
                return
            self._drag_pos = e.globalPos() - self.window().frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag_pos and e.buttons() == Qt.LeftButton:
            self.window().move(e.globalPos() - self._drag_pos)

    def mouseReleaseEvent(self, _e):
        self._drag_pos = None


# ── Main Window ───────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    """
    Top-level futuristic HUD window.

    Pass a GestureEngine instance; the window polls it via QTimer.
    """

    def __init__(self, engine=None):
        super().__init__()
        self._engine = engine
        self._startup_done = False

        # Frameless + translucent background ready
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setWindowTitle("Sasta Tony Stark — Gesture Controller")
        self.resize(1060, 670)

        # ── Central widget + layout ─────────────────────────────────────────
        central = QWidget()
        central.setStyleSheet("background: #0a0a0a;")
        self.setCentralWidget(central)

        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Title bar
        self._title_bar = TitleBar()
        self._title_bar.close_requested.connect(self.close)
        self._title_bar.minimize_requested.connect(self.showMinimized)
        root_layout.addWidget(self._title_bar)

        # Content row
        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(6, 6, 6, 6)
        content_layout.setSpacing(8)

        self._camera_view = CameraView()
        content_layout.addWidget(self._camera_view, stretch=1)

        self._hud_panel = HUDPanel()
        content_layout.addWidget(self._hud_panel, stretch=0)

        root_layout.addWidget(content, stretch=1)

        # Status bar
        self._status_bar = StatusBar()
        root_layout.addWidget(self._status_bar)

        # ── Startup overlay ─────────────────────────────────────────────────
        self._startup = StartupWidget(central)
        self._startup.setGeometry(central.rect())
        self._startup.show()
        self._startup.done.connect(self._on_startup_done)

        # ── UI refresh timer ────────────────────────────────────────────────
        self._ui_timer = QTimer(self)
        self._ui_timer.timeout.connect(self._refresh)
        self._ui_timer.start(33)  # ~30 fps

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if hasattr(self, "_startup"):
            self._startup.setGeometry(self.centralWidget().rect())

    def _on_startup_done(self):
        self._startup_done = True
        self._startup.hide()
        if self._engine:
            self._engine.start()

    def _refresh(self):
        self._camera_view.tick()
        self._hud_panel.tick()
        self._status_bar.tick()

        if not self._startup_done or self._engine is None:
            return

        state = self._engine.get_state()
        if state is None:
            return

        frame = state.get("frame")
        if frame is not None:
            self._camera_view.set_frame(frame)

        self._hud_panel.update_state(state)
        self._status_bar.set_message(state.get("status_message", ""))

    def closeEvent(self, e):
        if self._engine:
            self._engine.stop()
        super().closeEvent(e)
