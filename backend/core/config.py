FRAME_WINDOW = 16
ANOMALY_MODEL_PATH = "suspicious_actions.pth"
YOLO_MODEL_PATH = "yolov8n.onnx"
KINETICS_LABELS = "kinetics400_labels.json"
ACTIONS_TO_DETECT_CLASS_NAMES = [
    "normal", 
    "assault",
    "fall_floor",
    "hit",
    "jump",
    "kick",
    "punch",
    "run",
    "shoot_gun"
    "shoplift"
]

SECRET_KEY = "AIS_AI_SECRET_KEY"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

ACTIONS = {
    "shoplift": {
        "enabled": True,
        "sensitivity": 0.7,
    },
    "assault": {
        "enabled": True,
        "sensitivity": 0.8,
    },
    "fall_floor": {
        "enabled": True,
        "sensitivity": 0.6,
    },
    "jump": {
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
    "shoplift": "shoplift",
    "assault": "assault",
    "fall_floor": "fall_floor",
    "jump": "jump",
    "run": "run",
    "shoot_gun": "shoot_gun",
}

FRONTEND_LABELS = {
    "shoplift": "Кража",
    "assault": "Нападение",
    "fall_floor": "Падение",
    "jump": "Прыжок",
    "run": "Бег",
    "shoot_gun": "Стрельба из оружия",
    "normal": "Нормальное поведение",
}
