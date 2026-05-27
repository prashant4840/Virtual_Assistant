import json
from pathlib import Path


SETTINGS_PATH = Path(__file__).resolve().parent / "settings.json"

DEFAULT_SETTINGS = {
    "camera_index": 0,
    "theme": "dark",
    "menu_hold_seconds": 2.0,
    "mode_hold_seconds": 2.0,
    "gesture_interval_seconds": 1.2,
    "game_interval_seconds": 0.5,
    "swipe_left_threshold": -60,
    "swipe_right_threshold": 50,
    "pinch_minimize_threshold": 16,
    "pinch_close_threshold": 18,
    "pinch_smoothing_alpha": 0.3,
}


def _coerce_settings(raw: dict) -> dict:
    cfg = DEFAULT_SETTINGS.copy()
    cfg.update(raw or {})

    cfg["camera_index"] = int(cfg["camera_index"])
    cfg["theme"] = "light" if str(cfg["theme"]).lower() == "light" else "dark"
    cfg["menu_hold_seconds"] = float(cfg["menu_hold_seconds"])
    cfg["mode_hold_seconds"] = float(cfg["mode_hold_seconds"])
    cfg["gesture_interval_seconds"] = float(cfg["gesture_interval_seconds"])
    cfg["game_interval_seconds"] = float(cfg["game_interval_seconds"])
    cfg["swipe_left_threshold"] = int(cfg["swipe_left_threshold"])
    cfg["swipe_right_threshold"] = int(cfg["swipe_right_threshold"])
    cfg["pinch_minimize_threshold"] = int(cfg["pinch_minimize_threshold"])
    cfg["pinch_close_threshold"] = int(cfg["pinch_close_threshold"])
    cfg["pinch_smoothing_alpha"] = max(0.05, min(0.95, float(cfg["pinch_smoothing_alpha"])))
    return cfg


def load_settings() -> dict:
    if not SETTINGS_PATH.exists():
        save_settings(DEFAULT_SETTINGS.copy())
        return DEFAULT_SETTINGS.copy()

    try:
        data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        return _coerce_settings(data)
    except (json.JSONDecodeError, OSError, ValueError, TypeError):
        save_settings(DEFAULT_SETTINGS.copy())
        return DEFAULT_SETTINGS.copy()


def save_settings(settings: dict):
    cfg = _coerce_settings(settings)
    SETTINGS_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
