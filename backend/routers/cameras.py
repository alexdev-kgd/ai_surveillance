from fastapi import APIRouter, Depends, HTTPException
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from core.db import get_db
from core.cameras import CAMERAS
from core.camera_runtime import CAMERA_READERS
from core.audit_action import AuditAction
from services.rtsp_reader import RTSPCameraReader
from services.auth import get_current_user
from services.audit_log import log_action
from models.camera import Camera
from models.user import User
from schemas.camera import CameraCreate, CameraResponse, UsbCameraSyncRequest

router = APIRouter(prefix="/cameras", tags=["Cameras"])

def to_camera_response(camera: Camera) -> CameraResponse:
    device_id = None

    if str(camera.type).upper() == "USB" and camera.id.startswith("usb-"):
        device_id = camera.id[len("usb-") :]

    return CameraResponse(
        id=camera.id,
        name=camera.name,
        rtsp=camera.rtsp,
        type=camera.type,
        enabled=camera.enabled,
        device_id=device_id,
    )

@router.get("", response_model=list[CameraResponse])
async def get_cameras(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Camera))

    await log_action(db, user.id, AuditAction.CAMERA_SETTINGS_ACCESS)

    return [to_camera_response(camera) for camera in result.scalars().all()]


@router.post("", response_model=CameraResponse)
async def add_camera(
    payload: CameraCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    cam_id = f"ip-{uuid4().hex[:6]}"

    camera = Camera(
        id=cam_id,
        name=payload.name,
        rtsp=payload.rtsp,
        type="IP",
        enabled=True,
    )

    db.add(camera)
    await db.commit()

    reader = RTSPCameraReader(payload.rtsp, payload.name)
    reader.start()
    CAMERA_READERS[cam_id] = reader

    await log_action(
        db,
        user.id,
        AuditAction.CAMERA_ADDED,
        details={"message": f'Камера "{payload.name}" добавлена'}
    )

    return to_camera_response(camera)

@router.post("/usb/sync", response_model=list[CameraResponse])
async def sync_usb_cameras(
    payload: UsbCameraSyncRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    normalized_devices = {
        device.deviceId: (device.label.strip() or f"USB Camera {idx + 1}")
        for idx, device in enumerate(payload.devices)
        if device.deviceId.strip()
    }
    expected_ids = {f"usb-{device_id}" for device_id in normalized_devices}

    result = await db.execute(select(Camera).where(Camera.type == "USB"))
    existing_usb = {camera.id: camera for camera in result.scalars().all()}

    for device_id, label in normalized_devices.items():
        camera_id = f"usb-{device_id}"
        camera = existing_usb.get(camera_id)
        if camera is None:
            db.add(
                Camera(
                    id=camera_id,
                    name=label,
                    rtsp="",
                    type="USB",
                    enabled=False,
                )
            )
            continue

        if camera.name != label:
            camera.name = label

    for camera_id, camera in existing_usb.items():
        if camera_id in expected_ids:
            continue

        reader = CAMERA_READERS.pop(camera_id, None)
        if reader:
            reader.stop()
        await db.delete(camera)

    await db.commit()

    await log_action(
        db,
        user.id,
        AuditAction.CAMERA_SETTINGS_ACCESS,
        details={"message": "USB Камеры синхронизированы"},
    )

    refreshed = await db.execute(select(Camera))
    return [to_camera_response(camera) for camera in refreshed.scalars().all()]

@router.patch("/{camera_id}/toggle")
async def toggle_camera(
    camera_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Camera).where(Camera.id == camera_id)
    )
    camera = result.scalar_one_or_none()

    if not camera:
        raise HTTPException(404, "Camera not found")

    camera.enabled = not camera.enabled
    await db.commit()

    reader = CAMERA_READERS.get(camera_id)

    is_ip_camera = str(camera.type).upper() == "IP"

    if camera.enabled:
        if is_ip_camera and reader:
            reader.start()

        await log_action(
            db,
            user.id,
            AuditAction.CAMERA_ENABLED,
            details={"message": f'Камера "{camera.name}" включена'}
        )
    else:
        if is_ip_camera and reader:
            reader.stop()
        await log_action(
            db,
            user.id,
            AuditAction.CAMERA_DISABLED,
            details={"message": f'Камера "{camera.name}" выключена'}
        )

    return {"id": camera_id, "enabled": camera.enabled}

@router.delete("/{camera_id}")
async def delete_camera(
    camera_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Camera).where(Camera.id == camera_id)
    )
    camera = result.scalar_one_or_none()

    if not camera:
        raise HTTPException(404, "Camera not found")

    reader = CAMERA_READERS.pop(camera_id, None)
    if str(camera.type).upper() == "IP" and reader:
        reader.stop()

    await db.delete(camera)
    await db.commit()

    await log_action(
        db,
        user.id,
        AuditAction.CAMERA_DELETED,
        details={"message": f'Камера "{camera.name}" удалена'}
    )

    return {"status": "deleted"}
