# db.py —— 统一数据库层（PostgreSQL / SQLite 自动切换）
#
# 设计目标：
#   - 线上（Render）检测到 DATABASE_URL 环境变量 → 用 PostgreSQL（持久化，重启不丢）
#   - 本地开发（无 DATABASE_URL）        → 回退 SQLite（零依赖，开箱即用）
#   - 上层模块（chat_history / connectors / memory）只调本模块的 connect()/q()/exec()，
#     不关心底层是哪种数据库。
#
# 兼容处理：
#   - 占位符：SQLite 用 ?，PostgreSQL 用 %s → q() 自动转换
#   - INSERT OR IGNORE：pg 用 ON CONFLICT (id) DO NOTHING → convert() 自动改写
#   - 自增主键：SQLite 用 AUTOINCREMENT，pg 用 SERIAL → 在各自建表语句里区分
#   - 向量/JSON：统一以 TEXT 存 JSON 字符串，余弦相似度在 Python 端算（小规模够用，
#     无需 pgvector 扩展，免费版也能跑）

import os
import sqlite3
import logging

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "")
USE_PG = DATABASE_URL.startswith("postgres")

# Render 的 PostgreSQL 默认要求 sslmode=require，URL 里没带就补上
if USE_PG and "sslmode" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL + ("&" if "?" in DATABASE_URL else "?") + "sslmode=require"


# ===== PostgreSQL 连接池 =====
# 集中复用连接，避免每个请求新建连接打满 PG 连接数（免费版连接数有限）。
# SQLite 本地开发并发低，保持「每请求一连接」即可。
_PG_POOL = None


def _ensure_pool():
    """懒初始化线程安全连接池（仅 PG 模式）。失败则回退直连。"""
    global _PG_POOL
    if _PG_POOL is not None or not USE_PG:
        return
    try:
        import psycopg2
        from psycopg2 import pool as _pgpool
        _PG_POOL = _pgpool.ThreadedConnectionPool(1, 10, DATABASE_URL, connect_timeout=15)
    except Exception as e:  # noqa: BLE001
        logger.warning("[db] 连接池初始化失败，回退为每次新建连接: %s", e)
        _PG_POOL = None


def connect():
    """返回一个可用连接（pg 走连接池，sqlite 直接建）。

    pg 模式下会把连接实例的 .close() 重写为「归还池中」，
    因此上层模块现有的 conn.close() 写法无需改动即可复用连接池。
    """
    if USE_PG:
        _ensure_pool()
        if _PG_POOL is not None:
            try:
                conn = _PG_POOL.getconn()
                if getattr(conn, "closed", 0):
                    _PG_POOL.putconn(conn)
                    conn = _PG_POOL.getconn()
                _orig_close = getattr(conn, "close")

                def _return_to_pool():  # noqa: ANN202
                    try:
                        _PG_POOL.putconn(conn)
                    except Exception:  # noqa: BLE001
                        pass
                conn.close = _return_to_pool
                return conn
            except Exception as e:  # noqa: BLE001
                logger.warning("[db] 取池连接失败，回退直连: %s", e)
        import psycopg2
        return psycopg2.connect(DATABASE_URL, connect_timeout=15)
    else:
        from storage import DATA_DIR
        db_file = os.path.join(DATA_DIR, "conversations.db")
        conn = sqlite3.connect(db_file, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=DELETE")
        return conn


def q(sql: str) -> str:
    """把 SQL 里的 ? 占位符按当前方言改写（pg 用 %s）。

    还会把 SQLite 专有的「UPSERT」语法转成 PostgreSQL 等价写法：
      - INSERT OR IGNORE  → INSERT ... ON CONFLICT (id) DO NOTHING
      - INSERT OR REPLACE → INSERT ... ON CONFLICT (id) DO UPDATE SET <其余列>=EXCLUDED.<列>
    """
    if USE_PG:
        s = sql
        # INSERT OR IGNORE：冲突时整行忽略
        if "INSERT OR IGNORE" in s:
            s = (s
                 .replace("INSERT OR IGNORE INTO conversations", "INSERT INTO conversations")
                 .replace("INSERT OR IGNORE INTO messages", "INSERT INTO messages")
                 .replace("INSERT OR IGNORE INTO connectors", "INSERT INTO connectors"))
            if "ON CONFLICT" not in s:
                s = s + " ON CONFLICT (id) DO NOTHING"
        # INSERT OR REPLACE：冲突时按 EXCLUDED 更新其余列
        elif "INSERT OR REPLACE" in s:
            import re
            m = re.match(r"\s*INSERT OR REPLACE INTO (\w+)\s*\(([^)]+)\)", s)
            if m:
                table, cols = m.group(1), [c.strip() for c in m.group(2).split(",")]
                updates = ", ".join(f"{c}=EXCLUDED.{c}" for c in cols if c != "id")
                s = (s
                     .replace("INSERT OR REPLACE INTO " + table, "INSERT INTO " + table)
                     + f" ON CONFLICT (id) DO UPDATE SET {updates}")
            else:
                s = s.replace("INSERT OR REPLACE", "INSERT")
        s = s.replace("?", "%s")
        return s
    return sql


def exec(conn, sql: str, params: tuple = ()):
    """执行写操作并 commit。自动按方言转换 SQL。"""
    cur = conn.cursor()
    cur.execute(q(sql), params)
    conn.commit()
    return cur


def fetchall(conn, sql: str, params: tuple = ()):
    cur = conn.cursor()
    cur.execute(q(sql), params)
    return cur.fetchall()


def fetchone(conn, sql: str, params: tuple = ()):
    cur = conn.cursor()
    cur.execute(q(sql), params)
    return cur.fetchone()


def create_table_if_not_exists(conn, name: str, sqlite_ddl: str, pg_ddl: str):
    """按方言建表（自动按 ; 拆分多条语句，兼容 SQLite 单语句限制）。"""
    ddl = pg_ddl if USE_PG else sqlite_ddl
    cur = conn.cursor()
    for stmt in ddl.split(";"):
        s = stmt.strip()
        if s:
            cur.execute(s)
    conn.commit()
