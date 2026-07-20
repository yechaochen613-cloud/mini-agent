# 智伴私教 - Oracle Always Free 部署镜像
FROM python:3.11-slim

WORKDIR /app

# 先装依赖（利用 Docker 层缓存）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 再拷代码
COPY . .

EXPOSE 8000

CMD ["sh", "-c", "python -m uvicorn api:app --host 0.0.0.0 --port 8000"]
