# gesture_engine.py
# ─────────────────────────────────────────────────────────────
# UNCHANGED core logic extracted from VirtualAssistant.py
# DO NOT modify gesture recognition or system control code.
# ─────────────────────────────────────────────────────────────

import sys
import platform
import cv2
import mediapipe as mp
import numpy as np
import time
from collections import deque
import threading
import pyautogui as auto
import screen_brightness_control as sbc
from pynput.keyboard import Key, Controller

from HandTracking import HandDetector
from FaceTracking import face_filter
from settings_manager import load_settings

keyboard = Controller()
IS_WINDOWS = platform.system() == "Windows"
IS_DARWIN = platform.system() == "Darwin"

# ── Volume backend (Windows vs Mac) ───────────────────────────
if IS_WINDOWS:
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    volume = cast(interface, POINTER(IAudioEndpointVolume))

    def _set_volume(level: float):
        volume.SetMasterVolumeLevelScalar(level, None)

else:
    import subprocess
    def _set_volume(level: float):
        subprocess.call(["osascript", "-e",
                         f"set volume output volume {int(level * 100)}"])


def _task_switch(direction: str):
    """Switch app/window with OS-aware key mapping."""
    if IS_WINDOWS:
        auto.keyDown('win'); auto.press('tab'); auto.keyUp('win')
        auto.press('right' if direction == "right" else 'left')
        auto.press('enter')
    elif IS_DARWIN:
        # macOS: Command+Tab cycles apps; shift reverses direction.
        auto.keyDown('command')
        if direction == "left":
            auto.keyDown('shift')
        auto.press('tab')
        if direction == "left":
            auto.keyUp('shift')
        auto.keyUp('command')
    else:
        # Common Linux desktop workspace switch fallback.
        auto.hotkey('ctrl', 'alt', 'right' if direction == "right" else 'left')


def _minimize_window():
    if IS_WINDOWS:
        auto.hotkey('win', 'down')
    elif IS_DARWIN:
        auto.hotkey('command', 'm')
    else:
        auto.hotkey('alt', 'space')
        auto.press('n')


def _close_window():
    if IS_DARWIN:
        auto.hotkey('command', 'w')
    else:
        auto.hotkey('alt', 'f4')


def recognizeFingerJoin(hands: list) -> bool:
    settingFlag = True
    for hand in hands:
        neededPoints = [4, 8, 12, 16, 20]
        for neededPoint in neededPoints:
            for neededPoint2 in neededPoints:
                if (
                    abs(hand[neededPoint][2] - hand[neededPoint2][2]) < 20
                    and abs(hand[neededPoint][1] - hand[neededPoint2][1]) < 45
                ):
                    continue
                else:
                    settingFlag = False
    return settingFlag


def countFingers(hands: list) -> int:
    fingers = 0
    for hand in hands:
        fingerTips = [8, 12, 16, 20]
        for fingerTip in fingerTips:
            if hand[fingerTip][2] < hand[fingerTip - 2][2]:
                fingers += 1
        if hand[4][1] > hand[2][1]:
            fingers += 1
    return fingers


def volume_changer(length) -> float:
    volPer = np.interp(length, [0, 120], [0, 1])
    _set_volume(volPer)
    return volPer


def brightness_changer(length) -> float:
    bPer = np.interp(length, [0, 120], [0, 100])
    sbc.set_brightness(bPer)
    return bPer / 100.0


def get_pinch_length(hands: list):
    """Return distance between thumb tip and index tip."""
    if not hands:
        return None
    pt1 = (hands[0][4][1], hands[0][4][2])
    pt2 = (hands[0][8][1], hands[0][8][2])
    return int(np.hypot(pt2[0] - pt1[0], pt2[1] - pt1[1])), pt1, pt2


def gestures_control(hands: list, cfg: dict):
    if not hands:
        return
    pt1 = (hands[0][0][1], hands[0][0][2])
    pt2 = (hands[0][12][1], hands[0][12][2])
    thumb_pt = (hands[0][4][1], hands[0][4][2])
    index_pt = (hands[0][8][1], hands[0][8][2])
    middle_pt = (hands[0][12][1], hands[0][12][2])

    dist_thumb_index = int(np.hypot(thumb_pt[0] - index_pt[0], thumb_pt[1] - index_pt[1]))
    dist_thumb_middle = int(np.hypot(thumb_pt[0] - middle_pt[0], thumb_pt[1] - middle_pt[1]))
    x_diff = pt1[0] - pt2[0]

    if x_diff < cfg["swipe_left_threshold"]:
        _task_switch("right")
    elif x_diff > cfg["swipe_right_threshold"]:
        _task_switch("left")

    if dist_thumb_index < cfg["pinch_minimize_threshold"]:
        _minimize_window()
    if dist_thumb_middle < cfg["pinch_close_threshold"]:
        _close_window()


def game_remote(hands: list):
    if not hands:
        return
    pt1 = (hands[0][0][1], hands[0][0][2])
    pt2 = (hands[0][12][1], hands[0][12][2])
    x_diff = pt1[0] - pt2[0]

    if x_diff < -60:
        keyboard.press(Key.right); keyboard.release(Key.left)
    elif x_diff > 50:
        keyboard.press(Key.left); keyboard.release(Key.right)
    else:
        keyboard.release(Key.left); keyboard.release(Key.right)

    if hands[0][4][1] < hands[0][2][1]:
        keyboard.press('a')
    else:
        keyboard.release('a')


# ─── Engine State Object ───────────────────────────────────────

class GestureEngine:
    def __init__(self):
        self.config = load_settings()
        self.mp_face_detection = mp.solutions.face_detection
        self.hands_detector = HandDetector()
        self.face_detection = self.mp_face_detection.FaceDetection(
            model_selection=1, min_detection_confidence=0.4
        )

        self.rotation_turn1 = 0
        self.rotation_turn2 = 8
        self.rotation_turn3 = 0

        self.settingFlag = False
        self.toggleTimer = 0.0
        self.sub_toggleTimer = 0.0
        self.gesture_timer = 0.0
        self.selected = 0
        self.selected_already = False

        self.volume_level = 0.0
        self.brightness_level = 0.5
        self.finger_count = 0
        self.hands = []
        self.pinch_length = 0
        self.pinch_pt1 = (0, 0)
        self.pinch_pt2 = (0, 0)
        self.feedback_text = ""
        self.feedback_timer = 0.0
        self.pinch_smooth = None
        self._last_volume_sent = -1.0
        self._last_brightness_sent = -1.0
        self.current_fps = 0.0
        self._fps_lock = threading.Lock()
        self.exit_requested = False

        self.mode_handlers = {
            1: self._handle_gesture_mode,
            2: self._handle_game_mode,
            3: self._handle_volume_mode,
            4: self._handle_brightness_mode,
            5: self._handle_exit_mode,
        }

        self.mode_feedback = {
            1: "Gesture Controller Active",
            2: "Game Remote Active",
            3: "Volume Control Active",
            4: "Brightness Control Active",
            5: "Exit Requested",
        }

        self.cooldowns = {
            "switch": 0.0,
            "gesture": 0.0,
            "volume": 0.0,
            "brightness": 0.0,
        }

        self.mode_confidence_frames = 0
        self.required_confidence_frames = 8
        self.frame_times = deque(maxlen=60)
        self.performance_mode = "BALANCED"
        self.adaptive_fps = 0.0

    def _update_performance_metrics(self, dt: float):
        self.frame_times.append(dt)

        if len(self.frame_times) > 5:
            avg_dt = sum(self.frame_times) / len(self.frame_times)
            self.adaptive_fps = 1.0 / max(avg_dt, 0.0001)

            if self.adaptive_fps < 18:
                self.performance_mode = "POWER_SAVE"
            elif self.adaptive_fps < 28:
                self.performance_mode = "BALANCED"
            else:
                self.performance_mode = "PERFORMANCE"
def set_current_fps(self, fps: float):
    with self._fps_lock:
        self.current_fps = fps
        self.adaptive_fps = fps

def get_current_fps(self) -> float:
    with self._fps_lock:
        return self.current_fps

    def get_mode_name(self) -> str:
        names = {0: "IDLE", 1: "GESTURE CTRL", 2: "GAME MODE",
                 3: "VOLUME CTRL", 4: "BRIGHTNESS", 5: "EXIT"}
        return names.get(self.selected, "IDLE")

    def process(self, img, fps: float):
        """Run one frame of gesture logic. Returns annotated img."""
        dt = 1.0 / max(fps, 1)
        for key in self.cooldowns:
            self.cooldowns[key] = max(0.0, self.cooldowns[key] - dt)

        self._update_performance_metrics(dt)

        self.hands, img = self.hands_detector.giveAllPoints(img, connections=False)

        setting = False
        self.finger_count = 0

        if self.hands:
            setting = recognizeFingerJoin(self.hands)
            if not self.selected_already:
                self.finger_count = countFingers(self.hands)

        # pinch info for UI
        result = get_pinch_length(self.hands)
        if result:
            self.pinch_length, self.pinch_pt1, self.pinch_pt2 = result

        self.toggleTimer += dt

        if setting and self.toggleTimer >= self.config["menu_hold_seconds"]:
            if self.selected != 0:
                self.selected = 0
                self.sub_toggleTimer = 0.0
                self.pinch_smooth = None
            else:
                self.settingFlag = not self.settingFlag
            self.toggleTimer = 0
            self.selected_already = False

        if self.settingFlag:
            fingers = self.finger_count

            if fingers in self.mode_handlers or self.selected != 0:
                active_mode = self.selected if self.selected != 0 else fingers
                handler = self.mode_handlers.get(active_mode)

                if handler:
                    img = handler(img, dt, fingers)
            else:
                self.sub_toggleTimer = 0
                self.mode_confidence_frames = 0
                img, self.rotation_turn1, self.rotation_turn2, self.rotation_turn3 = face_filter(
                    self.face_detection, 0, img, True,
                    (self.rotation_turn1, self.rotation_turn2, self.rotation_turn3))
        else:
            self.mode_confidence_frames = 0
            img, self.rotation_turn1, self.rotation_turn2, self.rotation_turn3 = face_filter(
                self.face_detection, 0, img, False,
                (self.rotation_turn1, self.rotation_turn2, self.rotation_turn3))

        # feedback lifecycle
        if self.feedback_timer > 0:
            self.feedback_timer -= dt
            if self.feedback_timer <= 0:
                self.feedback_text = ""

        return img
    def _activate_mode(self, mode: int):
        self.selected = mode
        self.selected_already = True
        self.sub_toggleTimer = 0
        self.pinch_smooth = None
        self.cooldowns["switch"] = 0.4
        self.mode_confidence_frames = 0
        self.gesture_timer = 0
        self._set_feedback(self.mode_feedback.get(mode, "Mode Active"))

    def _update_face_filter(self, img, mode: int):
        return face_filter(
            self.face_detection,
            mode,
            img,
            True,
            (self.rotation_turn1, self.rotation_turn2, self.rotation_turn3),
            self.selected != 0,
        )

    def _validate_mode_selection(self, fingers: int, dt: float, mode: int) -> bool:
        if self.selected == mode:
            return True

        if self.cooldowns["switch"] > 0:
            return False

        if fingers == mode:
            self.mode_confidence_frames += 1
            self.sub_toggleTimer += dt
        else:
            self.mode_confidence_frames = 0
            self.sub_toggleTimer = 0

        if (
            self.mode_confidence_frames >= self.required_confidence_frames
            and self.sub_toggleTimer >= self.config["mode_hold_seconds"]
            and self.selected == 0
        ):
            self._activate_mode(mode)
            return True

        return self.selected == mode

    def _handle_gesture_mode(self, img, dt: float, fingers: int):
        if self._validate_mode_selection(fingers, dt, 1):
            if self.selected == 1:
                self.gesture_timer += dt
                if (
                    self.gesture_timer > self.config["gesture_interval_seconds"]
                    and self.cooldowns["gesture"] <= 0
                ):
                    gestures_control(self.hands, self.config)
                    self.gesture_timer = 0
                    self.cooldowns["gesture"] = 0.25

        img, self.rotation_turn1, self.rotation_turn2, self.rotation_turn3 = self._update_face_filter(img, 1)
        return img

    def _handle_game_mode(self, img, dt: float, fingers: int):
        if self._validate_mode_selection(fingers, dt, 2):
            if self.selected == 2:
                self.gesture_timer += dt
                if self.gesture_timer > self.config["game_interval_seconds"]:
                    game_remote(self.hands)
                    self.gesture_timer = 0

        img, self.rotation_turn1, self.rotation_turn2, self.rotation_turn3 = self._update_face_filter(img, 2)
        return img

    def _handle_volume_mode(self, img, dt: float, fingers: int):
        if self._validate_mode_selection(fingers, dt, 3):
            if self.selected == 3:
                result = get_pinch_length(self.hands)
                if result:
                    l, _, _ = result
                    alpha = self.config["pinch_smoothing_alpha"]
                    self.pinch_smooth = (
                        l if self.pinch_smooth is None
                        else ((1.0 - alpha) * self.pinch_smooth + alpha * l)
                    )

                    self.volume_level = float(np.interp(self.pinch_smooth, [0, 120], [0, 1]))

                    if (
                        abs(self.volume_level - self._last_volume_sent) >= 0.01
                        and self.cooldowns["volume"] <= 0
                    ):
                        self.volume_level = volume_changer(self.pinch_smooth)
                        self._last_volume_sent = self.volume_level
                        self.cooldowns["volume"] = 0.05
                        self._set_feedback(f"Volume {int(self.volume_level * 100)}%")

        img, self.rotation_turn1, self.rotation_turn2, self.rotation_turn3 = self._update_face_filter(img, 3)
        return img

    def _handle_brightness_mode(self, img, dt: float, fingers: int):
        if self._validate_mode_selection(fingers, dt, 4):
            if self.selected == 4:
                result = get_pinch_length(self.hands)
                if result:
                    l, _, _ = result
                    alpha = self.config["pinch_smoothing_alpha"]
                    self.pinch_smooth = (
                        l if self.pinch_smooth is None
                        else ((1.0 - alpha) * self.pinch_smooth + alpha * l)
                    )

                    self.brightness_level = float(np.interp(self.pinch_smooth, [0, 120], [0, 1]))

                    if (
                        abs(self.brightness_level - self._last_brightness_sent) >= 0.01
                        and self.cooldowns["brightness"] <= 0
                    ):
                        self.brightness_level = brightness_changer(self.pinch_smooth)
                        self._last_brightness_sent = self.brightness_level
                        self.cooldowns["brightness"] = 0.05
                        self._set_feedback(f"Brightness {int(self.brightness_level * 100)}%")

        img, self.rotation_turn1, self.rotation_turn2, self.rotation_turn3 = self._update_face_filter(img, 4)
        return img

    def _handle_exit_mode(self, img, dt: float, fingers: int):
        if self._validate_mode_selection(fingers, dt, 5):
            if self.selected == 5 or fingers == 5:
                self.exit_requested = True
                return img

        img, self.rotation_turn1, self.rotation_turn2, self.rotation_turn3 = self._update_face_filter(img, 5)
        return img

    def _set_feedback(self, text: str):
        self.feedback_text = text
        self.feedback_timer = 2.5

    def apply_settings(self, new_settings: dict):
        self.config.update(new_settings or {})
        self.required_confidence_frames = max(
            4,
            int(self.config.get("mode_hold_seconds", 1.5) * 5)
        )
        self._set_feedback("Settings updated")
