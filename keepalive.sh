#!/usr/bin/env bash
#
# keepalive.sh —— 防止 Render 免费实例休眠
#
# Render 免费 Web 服务在 15 分钟无 HTTP 流量后会自动休眠，
# 首访会触发冷启动页（SERVICE WAKING UP）。本脚本每 5 分钟 ping 一次
# 健康端点，保持实例活跃，避免访客看到冷启动页。
#
# 安装（crontab，每 5 分钟，替换 <PATH> 为本脚本绝对路径）：
#   (crontab -l 2>/dev/null | grep -v keepalive.sh; \
#    echo '*/5 * * * * <PATH>/keepalive.sh') | crontab -
#
# 查看日志：cat /tmp/keepalive.log
#
# 注意：
#   - 本地 cron 仅在电脑开机且联网时运行；Mac 合盖睡眠时不会执行。
#   - 若需 24x7 不依赖本机，改用云端监控（如 UptimeRobot，
#     监控 https://mini-agent-csde.onrender.com/health，间隔 5 分钟）。
#   - 已实测从本机直连 onrender.com 无需代理即可 200。

set -u

URLS=(
  "https://mini-agent-csde.onrender.com/health"
  "https://mini-agent-rbzb.onrender.com/health"
)

LOG="${KEEPALIVE_LOG:-/tmp/keepalive.log}"

ts() { date '+%Y-%m-%d %H:%M:%S'; }

for u in "${URLS[@]}"; do
  code=""
  for attempt in 1 2 3; do
    code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "$u" 2>/dev/null)
    if [ "$code" = "200" ]; then break; fi
    sleep 2
  done
  echo "$(ts) $u -> ${code:-ERR}" >> "$LOG"
done
