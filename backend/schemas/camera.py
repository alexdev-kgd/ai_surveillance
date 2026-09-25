from pydantic import BaseModel, Field

class CameraBase(BaseModel):
    name: str
    rtsp: str

class CameraCreate(CameraBase):
    pass

class CameraUpdate(BaseModel):
    name: str = Field(min_length=1)
    rtsp: str | None = None

class CameraResponse(CameraBase):
    id: str
    type: str
    enabled: bool
    device_id: str | None = None

    class Config:
        from_attributes = True

class UsbCameraDevice(BaseModel):
    deviceId: str
    label: str

class UsbCameraSyncRequest(BaseModel):
    devices: list[UsbCameraDevice]
