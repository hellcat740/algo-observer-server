"""
演示数据管理接口（X-API-Key 鉴权）。

供统一控制台的「演示数据」操作区调用：
- POST /api/admin/seed-demo   灌入演示数据（body: {"clear": true/false}）
- POST /api/admin/clear-demo  清空 product_id 以 DEMO- 开头的观测

种子生成是同步阻塞计算，用 run_in_threadpool 避免卡住事件循环。
"""
from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from .database import engine
from .seed import clear_demo, seed
from .auth import require_api_key

router = APIRouter(
    prefix="/api/admin",
    tags=["admin"],
    dependencies=[Depends(require_api_key)],
)


class SeedRequest(BaseModel):
    """灌数请求：clear=true 时先删除旧的 DEMO- 前缀观测再灌入。"""

    clear: bool = False


@router.post("/seed-demo")
async def seed_demo_endpoint(payload: SeedRequest):
    """灌入合成演示数据（⚠️ 仅演示用途）。"""
    result = await run_in_threadpool(seed, engine, payload.clear)
    return {
        "inserted": result["inserted"],
        "products": result["products"],
        "cleared": result["cleared"],
    }


@router.post("/clear-demo")
async def clear_demo_endpoint():
    """删除全部 DEMO- 前缀演示观测（不影响真实采集记录）。"""
    deleted = await run_in_threadpool(clear_demo, engine)
    return {"deleted": deleted}
