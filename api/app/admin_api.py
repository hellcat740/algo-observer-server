"""
演示数据与用户管理接口（X-API-Key 管理员密钥鉴权）。

供统一控制台的「演示数据」操作区调用：
- POST /api/admin/seed-demo   灌入演示数据（body: {"clear": true/false}）
- POST /api/admin/clear-demo  清空 product_id 以 DEMO- 开头的观测

用户管理（供控制台管理匿名用户档案）：
- GET    /api/admin/users                  用户列表（按 last_seen_at 倒序）
- DELETE /api/admin/users/{anonymous_id}   删除该用户的全部观测及 users 表建档

种子生成是同步阻塞计算，用 run_in_threadpool 避免卡住事件循环。
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .database import engine, get_db
from .models import Observation, User
from .schemas import AdminUserOut
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


# ---------- 用户管理 ----------

@router.get("/users", response_model=list[AdminUserOut])
def list_users(db: Session = Depends(get_db)):
    """匿名用户列表：按最近活跃时间（last_seen_at）倒序。"""
    return db.query(User).order_by(User.last_seen_at.desc()).all()


@router.delete("/users/{anonymous_id}")
def delete_user(anonymous_id: str, db: Session = Depends(get_db)):
    """删除指定匿名用户的全部观测（observations.user_ref == anonymous_id）及 users 表建档。

    用户不存在返回 404；成功返回删除的观测条数与建档删除标记。
    """
    user = db.query(User).filter(User.anonymous_id == anonymous_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )
    deleted_observations = (
        db.query(Observation)
        .filter(Observation.user_ref == anonymous_id)
        .delete(synchronize_session=False)
    )
    db.delete(user)
    db.commit()
    return {"deleted_observations": deleted_observations, "deleted_user": True}
