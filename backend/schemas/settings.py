from typing import Dict, Optional

from pydantic import BaseModel, Field


class ActionSettings(BaseModel):
    enabled: bool
    # Display sensitivity: controls on-screen labels (higher = easier to show)
    sensitivity: float = Field(ge=0.0, le=1.0)
    # Alert sensitivity: controls events/SMS (typically stricter / lower)
    # If omitted, backend derives a stricter value from sensitivity.
    alert_sensitivity: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class Settings(BaseModel):
    detection: Dict[str, ActionSettings]
    useObjectDetection: bool = True
