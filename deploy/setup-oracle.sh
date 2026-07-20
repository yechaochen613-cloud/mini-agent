#!/bin/bash
# ============================================================
# 智伴私教 - Oracle Always Free 一键部署脚本
# 用法：在 Oracle VM (Ubuntu 22.04) 上，git clone 后执行：
#   chmod +x setup-oracle.sh && ./setup-oracle.sh
# ============================================================
set -e

echo ">>> [1/5] 安装 Docker / docker-compose-plugin / ufw"
sudo apt-get update -y
sudo apt-get install -y docker.io docker-compose-plugin ufw curl git

echo ">>> [2/5] 启动 Docker 并设置开机自启"
sudo systemctl enable --now docker
sudo usermod -aG docker $USER

echo ">>> [3/5] 防火墙放行 22/80/443（8000 由 Nginx 反代，不直接暴露）"
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable

echo ">>> [4/5] 配置 .env"
if [ ! -f .env ]; then
  cat > .env <<'ENV'
# === 必填：智谱 GLM（或任意 OpenAI 兼容）===
OPENAI_API_KEY=你的智谱APIKey
OPENAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4
OPENAI_MODEL=glm-4-flash
MOCK=false

# === 数据库（docker-compose 内的 PostgreSQL）===
DB_PASSWORD=请改成强密码
DATABASE_URL=postgresql://miniagent:请改成强密码@db:5432/miniagent

# === 可选：GitHub OAuth（不填则登录按钮不可用）===
GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=
GITHUB_CALLBACK_URL=https://你的域名/ui/callback
ENV
  echo "已生成 .env 模板，请用 nano .env 填入真实密钥"
fi

echo ">>> [5/5] 构建并启动（restart: always 保证常驻）"
sudo docker compose up -d --build

echo ""
echo "✅ 部署完成！"
echo "   本机访问: curl http://localhost:8000/health"
echo "   公网: 用 Oracle 控制台分配的公网 IP，或绑定自己的域名 + Nginx 反代"
echo "   查看日志: sudo docker compose logs -f api"
