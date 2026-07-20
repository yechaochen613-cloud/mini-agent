# 智伴私教 · 迁移到 Oracle Always Free（真·常驻 / 不休眠 / 永久免费）

## 为什么选 Oracle Always Free

市面上标"免费"的平台（Render / Railway / Koyeb / Fly / Hugging Face / Vercel）**都会休眠或冷启动**，朋友打开要等几十秒甚至打不开。

**Oracle Cloud Free Tier "Always Free"** 是唯一同时满足这三个条件的：
- ✅ **永久免费**（4 个 ARM Ampere A1 核心 + 24GB RAM，或 2 个 AMD VM）
- ✅ **真·不休眠**（实例 7×24 运行，不像 Render 闲置 15 分钟就睡）
- ✅ **完整 Linux**（能跑 Docker、PostgreSQL、Nginx，随便折腾）
- ⚠️ 唯一门槛：注册需 **双币信用卡**（Visa/Master，仅验证不扣费），国内用户可能需尝试

> 备选：本机 Mac + 隧道（已配置好，见下方"当前状态"），但依赖 Mac 一直开机联网。

---

## 没有双币信用卡？（国内用户最常卡这步）

Oracle 注册**必须**双币信用卡验证（Visa/Master/AmEx，仅验证额度不扣费），这一步**只能本人完成**，无法由他人代持或绕过。你有两个出路：

1. **借/办一张家人的双币卡**过验证（Oracle 不查持卡人是否本人）—— 然后继续按本 README 走 Oracle 方案。
2. **改用国内云轻量应用服务器**（腾讯云/阿里云，约 60–100 元/年，微信/支付宝，无需双币卡，有固定公网 IP、7×24 不休眠）。部署命令与本方案完全一致，见 **[README-vm.md](./README-vm.md)**。

> 注册好 Oracle / 买到国内云 VM 后，把"公网 IP + SSH 连接方式"给开发，剩余部署（Docker 起服务、配库、绑域名）可远程代执行。

---

## 当前状态（本机方案已可用）

你的 Mac 上已经跑起常驻服务，并通过 `localhost.run` 隧道暴露：
- 公网地址：`https://f10eb6fdd43c37.lhr.life`（匿名隧道，**每次重连域名会变**，Mac 需保持开机；旧域名 `216c8d5a4e24d7.lhr.life` 已失效）
- 服务由 `launchd` 管理（开机自启 + 崩溃重启 + 防闲置睡眠）：`~/Library/LaunchAgents/com.zhiban.miniagent.plist`
- 启动脚本：`mini-agent/run_server.sh`（加载 `.env` 后起 uvicorn）

**朋友现在就能用这个链接。** 若要固定域名 + 关机也能用，往下看 Oracle 方案。

---

## Oracle 部署步骤

### 1. 注册 Oracle Cloud
- 打开 https://www.oracle.com/cloud/free/ ，用邮箱注册
- 验证双币信用卡（仅验证额度，不扣费）
- 创建 **Always Free** 实例：选 **ARM VM (Ampere, 4 OCPU, 24GB)** 或 **AMD VM (2 台)**
- 区域建议选离你近的（如东京、首尔、新加坡）
- 系统选 **Ubuntu 22.04**
- 创建时**下载/保存 SSH 私钥**（.key 文件）
- 在"实例详情"里把 **公网 IP** 记下来（这是固定 IP）

### 2. 开放端口
- Oracle 控制台 → 实例 → **Virtual Cloud Network (VCN)** → 安全列表 → 入站规则
- 放行 `22 (SSH)`、`80 (HTTP)`、`443 (HTTPS)`（TCP）

### 3. 登录 VM 并部署
```bash
# 本地终端
chmod 600 你的私钥.key
ssh -i 你的私钥.key ubuntu@<公网IP>

# 在 VM 里：
sudo apt install -y git
git clone https://github.com/yechaochen613-cloud/mini-agent.git
cd mini-agent/deploy
chmod +x setup-oracle.sh
./setup-oracle.sh
# 按提示 nano .env 填入智谱 API Key / DB 密码
sudo docker compose up -d --build   # 若脚本未自动起
```

### 4. 绑定域名 + HTTPS（可选但推荐）
- 把你的域名 A 记录指向 Oracle 公网 IP
- VM 上装 Nginx + Certbot 申请免费证书，反代到 `localhost:8000`
- 这样朋友访问 `https://你的域名` 稳定且不裸 IP

### 5. 验证
```bash
curl http://localhost:8000/health   # 应返回 {"status":"ok"}
# 浏览器打开 https://你的域名 或 http://<公网IP>:8000
```

---

## 数据库说明
- `db.py` 已支持：检测到 `DATABASE_URL` 走 PostgreSQL，否则回退 SQLite
- Oracle 方案用同实例 PostgreSQL（docker-compose 内的 `db` 服务），数据持久化到 `pgdata` 卷，实例不删就不丢
- 若想用 Oracle 自带 Autonomous DB 也行，把 `DATABASE_URL` 换成其连接串即可

## 回滚 / 停止
```bash
sudo docker compose down      # 停服务（数据卷保留）
```
