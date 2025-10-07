from ultralytics import YOLO
from config import YOLO_MODEL_PATH

yolo_model = YOLO(YOLO_MODEL_PATH)
yolo_model.overrides['verbose'] = False
