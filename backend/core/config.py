FRAME_WINDOW = 48
STRIDE = 4
ANOMALY_MODEL_PATH = "suspicious_actions_6classes.pth"
YOLO_MODEL_PATH = "yolov8n.onnx"
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
    "shoplift"
]

SECRET_KEY = "AIS_AI_SECRET_KEY"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

ACTIONS = {
    "assault": {
        "enabled": True,
        "sensitivity": 0.8,
    },
    "fall_floor": {
        "enabled": True,
        "sensitivity": 0.6,
    },
    "hit": {
        "enabled": False,
        "sensitivity": 0.5,
    },
    "jump": {
        "enabled": False,
        "sensitivity": 0.5,
    },
    "kick": {
        "enabled": False,
        "sensitivity": 0.5,
    },
    "punch": {
        "enabled": False,
        "sensitivity": 0.5,
    },
    "run": {
        "enabled": True,
        "sensitivity": 0.65,
    },
    "shoot_gun": {
        "enabled": True,
        "sensitivity": 0.9,
    },
    "shoplift": {
        "enabled": True,
        "sensitivity": 0.7,
    },
}

PERMISSIONS = [
    "users:read", "users:write",
    "streams:read", "events:read",
    "system:configure", "audit:read"
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
