"""
数据打包导出 / 导入接口（X-API-Key 鉴权）。

- GET  /api/export/bundle  下载 zip（支持 ?api_key= 便于浏览器直接下载）
- POST /api/import/bundle  multipart 上传 zip（幂等导入）
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile
from fastapi.concurrency import run_in_threadpool

from .auth import require_api_key
from .database import engine
from .transfer import TransferError, build_bundle, import_bundle

router = APIRouter(
    prefix="/api",
    tags=["transfer"],
    dependencies=[Depends(require_api_key)],
)

# zip 上传大小上限（本地演示足够，防误传超大文件）
MAX_UPLOAD_BYTES = 200 * 1024 * 1024


@router.get("/export/bundle")
async def export_bundle():
    """导出全部观测为 zip 数据包（格式 v1.0，已冻结）。"""
    data = await run_in_threadpool(build_bundle, engine)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    return Response(
        content=data,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename=observations-bundle-{ts}.zip"
        },
    )


@router.post("/import/bundle")
async def import_bundle_endpoint(file: UploadFile):
    """导入 zip 数据包：版本与 SHA-256 校验，逐条清洗，已存在记录幂等跳过。"""
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=422, detail="文件超过 200MB 上限")
    try:
        return await run_in_threadpool(import_bundle, engine, data)
    except TransferError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
