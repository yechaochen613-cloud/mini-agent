#!/bin/bash
# 常驻启动脚本：加载 .env 后启动 uvicorn（供 launchd 调用）
set -a
source /Users/tawei/WorkBuddy/2026-07-08-10-56-46/mini-agent/.env
set +a
exec /Users/tawei/.workbuddy/binaries/python/envs/default/bin/python -m uvicorn api:app --host 0.0.0.0 --port 8000
