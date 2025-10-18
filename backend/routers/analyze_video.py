import os
import tempfile
from fastapi import APIRouter, UploadFile, File
from fastapi.responses import JSONResponse
from services.media_utils import analyze_video_file

router = APIRouter(prefix="/analyze", tags=["Video Analysis"])

@router.post("/video/")
async def analyze_video(file: UploadFile = File(...)):
    suffix = os.path.splitext(file.filename)[-1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    result = analyze_video_file(tmp_path)
    os.remove(tmp_path)

    return JSONResponse(content=result)
