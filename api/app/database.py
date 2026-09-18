"""
数据库连接配置。

- DATABASE_URL 从环境变量读取；未配置时按运行环境选兜底：
  - Vercel 等无服务器环境：SQLite 放在 /tmp（函数实例本地盘，冷启动重建，
    仅适合演示；生产请在 Vercel 集成 Neon Postgres 等托管库后设 DATABASE_URL）；
  - 本地/自建服务器：当前目录下 obs_data.db；
  - docker-compose 部署：默认连容器内 PostgreSQL。
- 兼容 SQLite：sqlite URL 自动加 check_same_thread=False。
- UUID 在模型层用 String(36) 存储，保证 PostgreSQL 与 SQLite 行为一致。
"""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


def _default_database_url() -> str:
    if os.environ.get("VERCEL"):
        return "sqlite:////tmp/obs_data.db"
    if os.environ.get("DOCKER_COMPOSE"):
        return "postgresql+psycopg2://obs:obs@db:5432/observations"
    return "sqlite:///./obs_data.db"


DATABASE_URL = os.environ.get("DATABASE_URL", _default_database_url())

# SQLite 需要关闭同线程检查；PostgreSQL 不需要任何额外参数
_connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    _connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, connect_args=_connect_args, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI 依赖：每请求一个会话，结束自动关闭。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
