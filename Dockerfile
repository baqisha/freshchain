# 鲜智链 FreshChain FastAPI 调度服务镜像
FROM python:3.12-slim

WORKDIR /app

# 先装依赖，利用 Docker 层缓存
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 拷贝全部源码（main.py / orchestrator.py / db.py / seed_data.py / index.html / knowledge.md / SQL）
COPY . .

EXPOSE 8000

# 先灌入内置模拟数据（20 商品 + 45 天流水），再启动 uvicorn；
# MySQL 就绪由 docker-compose 的 healthcheck + depends_on 保证。
CMD ["sh", "-c", "python seed_data.py && uvicorn main:app --host 0.0.0.0 --port 8000"]
