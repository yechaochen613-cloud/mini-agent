# 智伴私教 · 部署到任意 Linux 云主机（真·常驻 / 不休眠）

本指南覆盖三种云主机，**部署步骤完全一样**（都是 Ubuntu 22.04 + Docker）：
- Oracle Cloud Always Free（永久免费，但注册需双币信用卡）
- 腾讯云轻量应用服务器（约 60–100 元/年，微信/支付宝，无需双币卡）
- 阿里云轻量应用服务器（同上）

> 区别**只在"你怎么拿到这台 VM"**，拿到之后下面的命令一字不差。

---

## 一、拿到一台 Ubuntu 22.04 云主机

### 方案1：Oracle Always Free（免费，需双币信用卡）
- 注册 https://www.oracle.com/cloud/free/ ，双币卡验证（仅验证额度，不扣费）
- 创建 Always Free 实例：选 **ARM VM (Ampere, 4 OCPU, 24GB)** 或 2 台 AMD VM
- 区域选近的（东京/首尔/新加坡），系统 Ubuntu 22.04
- 创建时保存 SSH 私钥（.key），记下公网 IP

### 方案2：腾讯云轻量应用服务器（付费，无双币卡门槛）
- 打开 https://cloud.tencent.com/product/lighthouse
- 选 **轻量应用服务器** → 镜像 **Ubuntu 22.04** → 地域近的
- 计费选"包年"（约 60–100 元/年）
- 创建后控制台给固定公网 IP，并在"防火墙"放行 22/80/443
- 用站内"一键登录"或密码/密钥 SSH 进去

### 方案3：阿里云轻量应用服务器（同上）
- https://www.aliyun.com/product/swas ，流程与腾讯云类似

---

## 二、登录 VM 并部署（三种云命令一致）

```bash
# 本地终端 SSH 进 VM
# Oracle: ssh -i 私钥.key ubuntu@<公网IP>
# 腾讯云/阿里云: ssh root@<公网IP>  或用控制台一键登录

# === 以下在 VM 内执行 ===
sudo apt update && sudo apt install -y git curl

# 拉代码
git clone https://github.com/yechaochen613-cloud/mini-agent.git
cd mini-agent/deploy

# 一键安装 Docker + 启动服务 + 开放端口
chmod +x setup-oracle.sh
./setup-oracle.sh
```

脚本会：装 Docker / Docker Compose → 用 `docker-compose.yml` 起 `api` + `db`(PostgreSQL) → 配置 `restart: always`（崩溃/重启自动拉起）。

## 三、填入密钥

编辑 `mini-agent/.env`（deploy 目录同级），至少填：

```
OPENAI_API_KEY=你的智谱key
OPENAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4/
OPENAI_MODEL=glm-4-flash
# DATABASE_URL 留空即可，docker-compose 内的 PostgreSQL 会自动接管
```

然后：
```bash
cd mini-agent/deploy
sudo docker compose up -d --build
```

## 四、验证

```bash
curl http://localhost:8000/health     # 期望 {"status":"ok"}
curl -N -X POST http://localhost:8000/chat/stream -H 'Content-Type: application/json' -d '{"message":"你好"}'
```

## 五、绑定域名 + HTTPS（推荐，非必须）

- 域名 A 记录指向 VM 公网 IP
- VM 内 `sudo apt install -y nginx certbot python3-certbot-nginx`
- `sudo certbot --nginx -d 你的域名` 申请免费证书
- Nginx 反代到 `localhost:8000`

之后朋友访问 `https://你的域名` 稳定且不裸 IP。

## 六、运维

```bash
sudo docker compose down          # 停（数据卷保留）
sudo docker compose up -d         # 起
sudo docker compose logs -f api   # 看日志
```

> 数据：PostgreSQL 落在 `pgdata` 卷，实例/容器不删就不丢。
