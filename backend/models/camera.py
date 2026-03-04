from sqlalchemy import String, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from models.base import Base

class Camera(Base):
    __tablename__ = "cameras"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    rtsp: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)  # IP / WEBCAM
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
