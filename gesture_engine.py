# gesture_engine.py
# Wraps the existing gesture recognition logic into a thread-safe GestureEngine class.
# All original functions from VirtualAssistant.py are preserved verbatim.

import cv2
import mediapipe as mp
import time
import threading
import numpy as np

# ── Optional Windows-only dependencies ─────────────────────────────────────
try:
    import pyautogui as auto
    AUTO_AVAILABLE = True
except Exception:
    auto = None
    AUTO_AVAILABLE = False

try:
    import screen_brightness_control as sbc
    SBC_AVAILABLE = True
except Exception:
    sbc = None
    SBC_AVAILABLE = False

try:
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    _devices = AudioUtilities.GetSpeakers()
    _interface = _devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    volume = cast(_interface, POINTER(IAudioEndpointVolume))
    VOLUME_AVAILABLE = True
except Exception:
    volume = None
    VOLUME_AVAILABLE = False

try:
    from pynput.keyboard import Key, Controller
    keyboard = Controller()
    KEYBOARD_AVAILABLE = True
except Exception:
    keyboard = None
    Key = None
    KEYBOARD_AVAILABLE = False

from FaceTracking import face_filter
from HandTracking import HandDetector


# ── Existing functions (verbatim from VirtualAssistant.py) ─────────────────

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


def transparent_circle(frame, center, radius, color, alpha=0.5):
    overlay = frame.copy()
    cv2.circle(overlay, center, radius, color, -1)
    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
    return frame


def transparent_rectangle(frame, x1, y1, x2, y2, color, alpha=0.5, boundary=cv2.FILLED):
    overlay = frame.copy()
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, boundary)
    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
    return frame


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


def volume_changer(length, img):
    volPer = np.interp(length, [0, 120], [0, 1])
    volBar = np.interp(length, [0, 120], [300, 60])
    volume.SetMasterVolumeLevelScalar(volPer, None)
    transparent_rectangle(img, 575, 60, 600, 300, (255, 210, 0), boundary=3)
    transparent_rectangle(img, 575, int(volBar), 600, 300, (255, 210, 0))
    cv2.putText(img, f'{int(volPer * 100)}%', (550, 50), cv2.FONT_HERSHEY_SIMPLEX,
                1, (255, 210, 0), 3)
    return img


def brightness_changer(length, img):
    bPer = np.interp(length, [0, 120], [0, 100])
    bBar = np.interp(length, [0, 120], [300, 60])
    sbc.set_brightness(bPer)
    transparent_rectangle(img, 575, 60, 600, 300, (255, 210, 0), boundary=3)
    transparent_rectangle(img, 575, int(bBar), 600, 300, (255, 210, 0))
    cv2.putText(img, f'{int(bPer)}%', (550, 50), cv2.FONT_HERSHEY_SIMPLEX,
                1, (255, 210, 0), 3)
    return img


def meter_manager(img, hands, type):
    if hands:
        pt1 = (hands[0][4][1], hands[0][4][2])
        pt2 = (hands[0][8][1], hands[0][8][2])
        img = cv2.line(img, pt1, pt2, (255, 210, 0), 5)
        img = cv2.circle(img, ((pt1[0] + pt2[0]) // 2, (pt1[1] + pt2[1]) // 2), 8, (200, 130, 0), cv2.FILLED)
        img = cv2.circle(img, pt1, 8, (200, 130, 0), cv2.FILLED)
        img = cv2.circle(img, pt2, 8, (200, 130, 0), cv2.FILLED)
        length = int(np.hypot(pt2[0] - pt1[0], pt2[1] - pt1[1]))
        if type == "V":
            img = volume_changer(length, img)
            return img
        elif type == "B":
            img = brightness_changer(length, img)
            return img
    return img


def volume_(img, hands):
    img = meter_manager(img, hands, type="V")
    return img


def brightness(img, hands):
    img = meter_manager(img, hands, type="B")
    return img


def gestures_control(img, hands):
    if hands:
        pt1 = (hands[0][0][1], hands[0][0][2])
        pt2 = (hands[0][12][1], hands[0][12][2])
        thumb_pt = (hands[0][4][1], hands[0][4][2])
        index_pt = (hands[0][8][1], hands[0][8][2])
        middle_pt = (hands[0][12][1], hands[0][12][2])
        dist_thumb_index = int(np.hypot(thumb_pt[0] - index_pt[0], thumb_pt[1] - index_pt[1]))
        dist_thumb_middle = int(np.hypot(thumb_pt[0] - middle_pt[0], thumb_pt[1] - middle_pt[1]))
        x_diff = pt1[0] - pt2[0]
        if x_diff < -60:
            img = cv2.circle(img, (600, 20), 10, (0, 255, 0), cv2.FILLED)
            if auto:
                auto.keyDown('win')
                auto.press('tab')
                auto.keyUp('win')
                auto.press('right')
                auto.press('enter')
        elif x_diff > 50:
            img = cv2.circle(img, (600, 20), 10, (0, 255, 0), cv2.FILLED)
            if auto:
                auto.keyDown('win')
                auto.press('tab')
                auto.keyUp('win')
                auto.press('left')
                auto.press('enter')
        if dist_thumb_index < 16:
            if auto:
                auto.keyDown('win')
                auto.press('down')
                auto.keyUp('win')
        if dist_thumb_middle < 18:
            if auto:
                auto.keyDown('alt')
                auto.press('f4')
                auto.keyUp('alt')
    return img


def game_remote(img, hands):
    if hands:
        pt1 = (hands[0][0][1], hands[0][0][2])
        pt2 = (hands[0][12][1], hands[0][12][2])
        x_diff = pt1[0] - pt2[0]
        if x_diff < -60:
            img = cv2.circle(img, (600, 20), 10, (0, 255, 0), cv2.FILLED)
            if keyboard:
                keyboard.press(Key.right)
                keyboard.release(Key.left)
        elif x_diff > 50:
            img = cv2.circle(img, (600, 20), 10, (0, 255, 0), cv2.FILLED)
            if keyboard:
                keyboard.press(Key.left)
                keyboard.release(Key.right)
        else:
            if keyboard:
                keyboard.release(Key.left)
                keyboard.release(Key.right)
        if hands[0][4][1] < hands[0][2][1]:
            if keyboard:
                keyboard.press('a')
        else:
            if keyboard:
                keyboard.release('a')
    return img


# ── GestureEngine class ─────────────────────────────────────────────────────

class GestureEngine:
    """
    Wraps the gesture recognition loop in a background thread and exposes
    a thread-safe state snapshot consumed by the UI layer.
    """

    MODE_NAMES = {
        0: "IDLE",
        1: "GESTURE CTRL",
        2: "GAME MODE",
        3: "VOLUME CTRL",
        4: "BRIGHTNESS",
        5: "EXIT",
    }

    def __init__(self):
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread = None

        # ── Publicly readable state ────────────────────────────────────────
        self.frame = None            # Current processed BGR frame
        self.finger_count = 0
        self.selected_mode = 0       # 0=idle, 1–5 as above
        self.volume_level = 50.0     # 0–100
        self.brightness_level = 50.0 # 0–100
        self.fps = 0.0
        self.setting_flag = False
        self.is_active = False       # True when a hand is visible
        self.status_message = "Initializing..."
        self.camera_ready = False

        # Seed volume/brightness from system on creation
        if VOLUME_AVAILABLE:
            try:
                self.volume_level = volume.GetMasterVolumeLevelScalar() * 100
            except Exception:
                pass
        if SBC_AVAILABLE:
            try:
                bright = sbc.get_brightness()
                if bright:
                    self.brightness_level = float(bright[0])
            except Exception:
                pass

    # ── Public API ─────────────────────────────────────────────────────────

    def start(self):
        """Start the gesture processing thread."""
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        """Signal the processing thread to stop and wait for it."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=3.0)

    def get_state(self) -> dict:
        """Return a thread-safe snapshot of the current state."""
        with self._lock:
            return {
                "frame": self.frame.copy() if self.frame is not None else None,
                "finger_count": self.finger_count,
                "selected_mode": self.selected_mode,
                "volume_level": self.volume_level,
                "brightness_level": self.brightness_level,
                "fps": self.fps,
                "setting_flag": self.setting_flag,
                "is_active": self.is_active,
                "status_message": self.status_message,
                "camera_ready": self.camera_ready,
            }

    # ── Background processing loop ─────────────────────────────────────────

    def _run(self):
        """Main gesture-recognition loop (logic from VirtualAssistant.main())."""
        cap = cv2.VideoCapture(0)
        cap.set(4, 240)
        cap.set(5, 480)

        mp_face_detection = mp.solutions.face_detection
        handsDetector = HandDetector()
        face_detection_obj = mp_face_detection.FaceDetection(
            model_selection=1, min_detection_confidence=0.4
        )

        rotation_turn1 = 0
        rotation_turn2 = 8
        rotation_turn3 = 0

        pTime = 0.0
        settingFlag = False
        toggleTimer = 0.0
        sub_toggleTimer = 0.0
        gesture_timer = 0.0
        selected = 0
        selected_already = False

        with self._lock:
            self.camera_ready = True
            self.status_message = "Camera Ready"

        while not self._stop_event.is_set():
            ret, img = cap.read()
            if not ret:
                time.sleep(0.01)
                continue

            hands, img = handsDetector.giveAllPoints(img, connections=False)

            cTime = time.time()
            elapsed = cTime - pTime
            fps = 1.0 / elapsed if elapsed > 0 else 30.0
            pTime = cTime

            setting = False
            fingers = 0
            if hands:
                setting = recognizeFingerJoin(hands)
                if not selected_already:
                    fingers = countFingers(hands)

            toggleTimer += 1.0 / fps

            if setting and toggleTimer >= 2:
                if selected != 0:
                    selected = 0
                else:
                    settingFlag = not settingFlag
                toggleTimer = 0.0
                selected_already = False
                dot_color = (0, 255, 0) if settingFlag else (0, 0, 255)
                img = cv2.circle(img, (600, 20), 10, dot_color, cv2.FILLED)

            prev_img = img
            try:
                if settingFlag:
                    if fingers == 1 or selected == 1:
                        sub_toggleTimer += 1.0 / fps
                        if sub_toggleTimer >= 2 and selected == 0:
                            sub_toggleTimer = 0.0
                            selected = 1
                            selected_already = True
                        if selected == 1:
                            gesture_timer += 1.0 / fps
                            if gesture_timer > 1.2:
                                img = gestures_control(img, hands)
                                gesture_timer = 0.0
                        result = face_filter(
                            face_detection_obj, 1, img, True,
                            (rotation_turn1, rotation_turn2, rotation_turn3),
                            not selected == 0,
                        )
                        if result is not None:
                            img, rotation_turn1, rotation_turn2, rotation_turn3 = result

                    elif fingers == 2 or selected == 2:
                        sub_toggleTimer += 1.0 / fps
                        if sub_toggleTimer >= 2 and selected == 0:
                            sub_toggleTimer = 0.0
                            selected = 2
                            selected_already = True
                        if selected == 2:
                            gesture_timer += 1.0 / fps
                            if gesture_timer > 0.5:
                                img = game_remote(img, hands)
                                gesture_timer = 0.0
                        result = face_filter(
                            face_detection_obj, 2, img, True,
                            (rotation_turn1, rotation_turn2, rotation_turn3),
                            not selected == 0,
                        )
                        if result is not None:
                            img, rotation_turn1, rotation_turn2, rotation_turn3 = result

                    elif fingers == 3 or selected == 3:
                        sub_toggleTimer += 1.0 / fps
                        if sub_toggleTimer >= 2 and selected == 0:
                            sub_toggleTimer = 0.0
                            selected = 3
                            selected_already = True
                        if selected == 3:
                            try:
                                img = volume_(img, hands)
                                if VOLUME_AVAILABLE:
                                    self.volume_level = volume.GetMasterVolumeLevelScalar() * 100
                            except Exception:
                                pass
                        result = face_filter(
                            face_detection_obj, 3, img, True,
                            (rotation_turn1, rotation_turn2, rotation_turn3),
                            not selected == 0,
                        )
                        if result is not None:
                            img, rotation_turn1, rotation_turn2, rotation_turn3 = result

                    elif fingers == 4 or selected == 4:
                        sub_toggleTimer += 1.0 / fps
                        if sub_toggleTimer >= 2 and selected == 0:
                            sub_toggleTimer = 0.0
                            selected = 4
                            selected_already = True
                        if selected == 4:
                            try:
                                img = brightness(img, hands)
                                if SBC_AVAILABLE:
                                    bright = sbc.get_brightness()
                                    if bright:
                                        self.brightness_level = float(bright[0])
                            except Exception:
                                pass
                        result = face_filter(
                            face_detection_obj, 4, img, True,
                            (rotation_turn1, rotation_turn2, rotation_turn3),
                            not selected == 0,
                        )
                        if result is not None:
                            img, rotation_turn1, rotation_turn2, rotation_turn3 = result

                    elif fingers == 5:
                        sub_toggleTimer += 1.0 / fps
                        if sub_toggleTimer >= 2 and selected == 0:
                            self._stop_event.set()
                            break
                        result = face_filter(
                            face_detection_obj, 5, img, True,
                            (rotation_turn1, rotation_turn2, rotation_turn3),
                            not selected == 0,
                        )
                        if result is not None:
                            img, rotation_turn1, rotation_turn2, rotation_turn3 = result

                    else:
                        sub_toggleTimer = 0.0
                        result = face_filter(
                            face_detection_obj, 0, img, True,
                            (rotation_turn1, rotation_turn2, rotation_turn3),
                        )
                        if result is not None:
                            img, rotation_turn1, rotation_turn2, rotation_turn3 = result

                else:
                    result = face_filter(
                        face_detection_obj, 0, img, False,
                        (rotation_turn1, rotation_turn2, rotation_turn3),
                    )
                    if result is not None:
                        img, rotation_turn1, rotation_turn2, rotation_turn3 = result

            except TypeError:
                img = prev_img

            # Determine status text
            if hands:
                status = "HAND DETECTED — TRACKING"
                is_active = True
            elif settingFlag:
                status = "SCANNING FOR HAND..."
                is_active = False
            else:
                status = "IDLE — MAKE A FIST TO OPEN MENU"
                is_active = False

            # Push state to shared memory
            with self._lock:
                self.frame = img
                self.finger_count = fingers
                self.selected_mode = selected
                self.setting_flag = settingFlag
                self.fps = fps
                self.is_active = is_active
                self.status_message = status

        cap.release()
