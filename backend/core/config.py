# Aligned with training / serve (`utils.video_preprocess.CLIP_LEN` / `SAMPLE_STRIDE`)
STRIDE = 2

ANOMALY_MODEL_PATH = "suspicious_actions_best.pth"
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
    "shoot_gun",
    "shoplift",
]

SECRET_KEY = "AIS_AI_SECRET_KEY"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

# sensitivity: higher → lower confidence threshold (more detections).
# alert_sensitivity: used for events/notifications; typically lower than
# display sensitivity so alerts require higher confidence.
# High-cost classes (fall_floor, shoot_gun) use stricter (lower) values.
ACTIONS = {
    "assault": {
        "enabled": True,
        "sensitivity": 0.75,
        "alert_sensitivity": 0.55,
    },
    "fall_floor": {
        "enabled": True,
        # raised threshold vs old 0.6 → fewer standing→fall false positives
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
    "shoot_gun": {
        "enabled": True,
        # old 0.9 was very loose (threshold ~0.27); raise confidence bar
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

DEFAULT_SETTINGS = {
    "detection": ACTIONS,
    "useObjectDetection": False,
}

CLASS_TO_ACTION = {
    "assault": "assault",
    "fall_floor": "fall_floor",
    "hit": "hit",
    "jump": "jump",
    "kick": "kick",
    "punch": "punch",
    "run": "run",
    "shoot_gun": "shoot_gun",
    "shoplift": "shoplift",
}

FRONTEND_LABELS = {
    "assault": "Нападение",
    "fall_floor": "Падение",
    "hit": "Удар",
    "jump": "Прыжок",
    "kick": "Удар ногой",
    "punch": "Удар кулаком",
    "run": "Бег",
    "shoot_gun": "Стрельба из оружия",
    "shoplift": "Кража",
    "normal": "Нормальное поведение",
}
