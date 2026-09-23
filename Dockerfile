# 算法歧视观测服务 · 阿里云 ECS 生产镜像
# 构建:  docker build -t algo-observer:main .
# 运行:  见 docker-compose.yml（推荐）

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# pip 源默认走阿里云 VPC 内网镜像：不占 ECS 公网带宽（1Mbps 机器的关键），且不限速
# 在阿里云 ECS 之外构建时，用 --build-arg PIP_INDEX_URL=https://pypi.org/simple 覆盖
ARG PIP_INDEX_URL=https://mirrors.cloud.aliyuncs.com/pypi/simple/

# 先装依赖，充分利用构建缓存
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i ${PIP_INDEX_URL}

# 再拷贝应用代码
COPY api/ ./api/

WORKDIR /app/api

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)" || exit 1

# 启动时 init_db() 会自动建表 + 轻量迁移，全新 Postgres 无需手工 DDL
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
