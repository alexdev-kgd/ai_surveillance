FRAME_WINDOW = 32
ANOMALY_MODEL_PATH = "suspicious_actions.pth"
KINETICS_LABELS = "kinetics400_labels.json"

SECRET_KEY = "AIS_AI_SECRET_KEY"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

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
    "system:configure"
]

ROLES = {
        "ADMIN": PERMISSIONS,
        "OPERATOR": ["streams:read"],
}

DEFAULT_SETTINGS = {
    "detection": ACTIONS
}

CLASS_TO_ACTION = {
    "shoplift": "shoplift",
    "assault": "assault",
    "fall_floor": "fall_floor",
    "jump": "jump",
    "run": "run",
    "shoot_gun": "shoot_gun",
}
