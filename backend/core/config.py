import os
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def load_secret_key():
    key = os.environ.get("SECRET_KEY", "")
    if len(key.encode("utf-8")) < 32 or key == "AIS_AI_SECRET_KEY":
        raise RuntimeError("Set SECRET_KEY to a randomly generated secret of at least 32 bytes")
    return key


def load_cors_origins():
    origins = [s.strip() for s in os.environ.get("CORS_ORIGINS", "").split(",") if s.strip()]
    for origin in origins:
        parsed = urlsplit(origin)
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                or "*" in origin or parsed.username is not None
                or parsed.password is not None or parsed.path
                or parsed.query or parsed.fragment):
            raise RuntimeError("CORS_ORIGINS must contain exact HTTP(S) origins without paths or wildcards")
        try:
            parsed.port
        except ValueError as exc:
            raise RuntimeError("Invalid port in CORS_ORIGINS") from exc
    return origins


CORS_ORIGINS = load_cors_origins()

# Aligned with training / serve (`utils.video_preprocess.CLIP_LEN` / `SAMPLE_STRIDE`)
STRIDE = 2

ANOMALY_MODEL_PATH = "suspicious_actions_best.pth"
ANOMALY_YOLO_MODEL_PATH = "suspicious_actions_yolo_best.pth"
YOLO_MODEL_PATH = "yolov8n.onnx"

# Post-model gates (P3)
ENABLE_FALL_POSE_GATE = True
ENABLE_WEAPON_THREAT_GATE = True

ACTIONS_TO_DETECT_CLASS_NAMES = [
    "normal",
    "assault",
    "fall_floor",
    "hit",
    "jump",
    "kick",
    "punch",
    "run",
    "hold_weapon",
    "shoplift",
]

SECRET_KEY = load_secret_key()
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

# sensitivity: higher → lower confidence threshold (more detections).
# alert_sensitivity: used for events/notifications; typically lower than
# display sensitivity so alerts require higher confidence.
# High-cost classes (fall_floor, hold_weapon) use stricter (lower) values.
ACTIONS = {
    "assault": {
        "enabled": True,
        "sensitivity": 0.75,
        "alert_sensitivity": 0.55,
    },
    "fall_floor": {
        "enabled": True,
        "sensitivity": 0.35,
        "alert_sensitivity": 0.20,
    },
    "hit": {
        "enabled": False,
        "sensitivity": 0.5,
        "alert_sensitivity": 0.35,
    },
    "jump": {
        "enabled": False,
        "sensitivity": 0.5,
        "alert_sensitivity": 0.35,
    },
    "kick": {
        "enabled": False,
        "sensitivity": 0.5,
        "alert_sensitivity": 0.35,
    },
    "punch": {
        "enabled": False,
        "sensitivity": 0.5,
        "alert_sensitivity": 0.35,
    },
    "run": {
        "enabled": True,
        "sensitivity": 0.55,
        "alert_sensitivity": 0.40,
    },
    "hold_weapon": {
        "enabled": True,
        "sensitivity": 0.30,
        "alert_sensitivity": 0.15,
    },
    "shoplift": {
        "enabled": True,
        "sensitivity": 0.60,
        "alert_sensitivity": 0.45,
    },
}

PERMISSIONS = [
    "users:read", "users:write",
    "streams:read", "events:read",
    "system:configure", "audit:read",
]

ROLES = {
    "ADMIN": PERMISSIONS,
    "OPERATOR": ["streams:read"],
}

FRONTEND_LABELS = {
    "assault": "Нападение",
    "fall_floor": "Падение",
    "hit": "Удар",
    "jump": "Прыжок",
    "kick": "Удар ногой",
    "punch": "Удар кулаком",
    "run": "Бег",
    "hold_weapon": "Оружие в руках",
    "shoplift": "Кража",
    "normal": "Нормальное поведение",
}

DEFAULT_SETTINGS = {
    "detection": ACTIONS,
    "useObjectDetection": False,
    "actionLabels": dict(FRONTEND_LABELS),
}

# Stored settings and older checkpoints used shoot_gun before the class rename.
LEGACY_ACTION_ALIASES = {
    "shoot_gun": "hold_weapon",
}

CLASS_TO_ACTION = {
    "assault": "assault",
    "fall_floor": "fall_floor",
    "hit": "hit",
    "jump": "jump",
    "kick": "kick",
    "punch": "punch",
    "run": "run",
    "hold_weapon": "hold_weapon",
    "shoot_gun": "hold_weapon",
    "shoplift": "shoplift",
}
