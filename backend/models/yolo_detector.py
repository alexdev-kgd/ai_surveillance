from ultralytics import YOLO
from core.config import YOLO_MODEL_PATH

yolo_model = YOLO(YOLO_MODEL_PATH)

yolo_model.overrides['device'] = 0
yolo_model.overrides['verbose'] = False
