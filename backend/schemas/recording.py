from typing import Literal

from pydantic import BaseModel, Field


class RecordingSettings(BaseModel):
    enabled: bool = False
    clip_limit_mode: Literal["size", "duration"] = "size"
    max_clip_size_mb: int = Field(default=100, ge=1, le=2048)
    max_clip_duration_seconds: int = Field(default=300, ge=1, le=86400)
    camera_enabled: dict[str, bool] = Field(default_factory=dict)
    directory: str = Field(default="saved_recordings", min_length=1)
