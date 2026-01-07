FRAME_WINDOW = 32
ANOMALY_MODEL_PATH = "suspicious_actions.pth"
KINETICS_LABELS = "kinetics400_labels.json"

SECRET_KEY = "AIS_AI_SECRET_KEY"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

ACTIONS = {
        "shoplift": True,
        "assault": True,
        "fall_floor": True,
        "jump": False,
        "run": True,
        "shoot_gun": True,
}

DEFAULT_SETTINGS = {
    "detection": ACTIONS,
    "sensitivity": 0.6,
}
