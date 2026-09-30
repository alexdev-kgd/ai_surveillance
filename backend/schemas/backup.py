from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class BackupScheduleConfig(BaseModel):
    enabled: bool = False
    mode: Literal["interval", "daily"] = "interval"
    interval_hours: int = Field(default=24, ge=1, le=720)
    daily_time: str = Field(default="08:00", pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")


class BackupSchedule(BackupScheduleConfig):
    next_run_at: datetime | None = None
    last_run_at: datetime | None = None
    last_error: str | None = None


class BackupFile(BaseModel):
    name: str
    size_bytes: int
    created_at: datetime
