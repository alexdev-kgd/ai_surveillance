import os
import tempfile
from fastapi import APIRouter, Depends, UploadFile, File
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from core.db import get_db
from core.audit_action import AuditAction
from services.media_utils import analyze_video_file
from services.auth import get_current_user
from services.audit_log import log_action

router = APIRouter(prefix="/analyze", tags=["Video Analysis"])

@router.post("/video/")
async def analyze_video(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):
    suffix = os.path.splitext(file.filename)[-1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    result = analyze_video_file(tmp_path)
    os.remove(tmp_path)

    await log_action(db, user.id, AuditAction.VIDEO_ANALYSIS)

    return JSONResponse(content=result)
