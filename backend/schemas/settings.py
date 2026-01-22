from pydantic import BaseModel, Field
from typing import Dict

class ActionSettings(BaseModel):
    enabled: bool
    sensitivity: float = Field(ge=0.0, le=1.0)

class Settings(BaseModel):
    detection: Dict[str, ActionSettings]
    useObjectDetection: bool = True
