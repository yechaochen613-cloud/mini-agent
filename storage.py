# storage.py
# ============================================================
# 统一持久化数据目录（SqliteSaver 方案的基座）。
#
# 数据放在哪，决定部署后重启 / redeploy 数据丢不丢：
#   1) 优先取环境变量 RENDER_DISK_MOUNT_PATH（Render Disk 挂载点，例如 /var/data），
#      数据落到 <挂载点>/mini-agent —— 这是部署后数据不丢的关键（Render Disk 跨 redeploy 保留）。
#   2) 否则回退到项目内 data/ 目录 —— 本地开发、未挂盘时也能正常跑。
#
# 所有需要持久化的东西都集中放这里：对话历史 SQLite、文档索引 JSON、上传文件、
# Agent 长期记忆、用户笔记。这样挂载 Disk 后，整盘数据都在持久卷上。
# ============================================================

import os
import shutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _resolve_data_dir() -> str:
    mnt = os.getenv("RENDER_DISK_MOUNT_PATH")
    d = os.path.join(mnt, "mini-agent") if mnt else os.path.join(BASE_DIR, "data")
    os.makedirs(d, exist_ok=True)
    os.makedirs(os.path.join(d, "uploads"), exist_ok=True)
    return d


# 统一数据根目录（模块加载即确定）
DATA_DIR = _resolve_data_dir()
# 上传文件目录
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")


def _move_file(src: str, dst: str) -> None:
    """若 src 存在且 dst 不存在，把 src 搬到 dst（幂等，失败静默）。"""
    if not os.path.exists(src) or os.path.exists(dst):
        return
    try:
        shutil.move(src, dst)
    except OSError:
        pass


def migrate_legacy() -> None:
    """一次性把项目根目录下的旧数据文件 / 目录搬到 DATA_DIR（幂等，不覆盖已有文件）。
    注意：对话历史 conversations.json 由 chat_history 负责迁移进 SQLite，这里不碰。"""
    for name in ("documents.json", "notes.json", "memory.json"):
        _move_file(os.path.join(BASE_DIR, name), os.path.join(DATA_DIR, name))

    old_up = os.path.join(BASE_DIR, "uploads")
    if os.path.isdir(old_up):
        for fn in os.listdir(old_up):
            _move_file(os.path.join(old_up, fn), os.path.join(UPLOAD_DIR, fn))
        try:
            if not os.listdir(old_up):
                os.rmdir(old_up)
        except OSError:
            pass


# 模块加载时执行一次旧数据迁移（仅搬 JSON/上传目录，对话历史留给 chat_history）
migrate_legacy()
