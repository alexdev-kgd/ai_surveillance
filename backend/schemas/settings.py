# schemas.py
from pydantic import BaseModel

class DetectionSettings(BaseModel):
	shoplift: bool
	assault: bool
	fall_floor: bool
	jump: bool
	run: bool
	shoot_gun: bool

class Settings(BaseModel):
    detection: DetectionSettings
    sensitivity: float
