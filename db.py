import os
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

from config import DATABASE_URL

db_pool = None
_mem = {}  # fallback in-memory khi chưa cấu hình DATABASE_URL
_schema_ready = False

SCHEMA_SQL = (
    "CREATE TABLE IF NOT EXISTS points ("
    " user_id BIGINT PRIMARY KEY,"
    " points  INTEGER NOT NULL DEFAULT 0,"
    " msgs    INTEGER NOT NULL DEFAULT 0,"
    " last    TIMESTAMP"
    ");"
)


def _clean_dsn(dsn: str) -> str:
    """asyncpg không hiểu một số param của Neon (vd channel_binding)."""
    u = urlparse(dsn)
    q = [(k, v) for k, v in parse_qsl(u.query) if k.lower() != "channel_binding"]
    return urlunparse(u._replace(query=urlencode(q)))


async def _ensure_schema():
    global _schema_ready
    if _schema_ready or db_pool is None:
        return
    async with db_pool.acquire() as conn:
        await conn.execute(SCHEMA_SQL)
    _schema_ready = True


async def init_db():
    global db_pool
    if not DATABASE_URL:
        print("DATABASE_URL chưa cấu hình - dùng in-memory cho points.", flush=True)
        return
    import asyncpg

    dsn = _clean_dsn(DATABASE_URL)
    pool = await asyncpg.create_pool(
        dsn, min_size=1, max_size=5, statement_cache_size=0
    )
    async with pool.acquire() as conn:
        await conn.execute(SCHEMA_SQL)
    db_pool = pool
    _schema_ready = True
    print("Đã kết nối DB points thành công 🐟", flush=True)


async def add_points(user_id: int, n: int):
    if db_pool is None:
        _mem[user_id] = _mem.get(user_id, 0) + n
        return
    try:
        await _ensure_schema()
        await db_pool.execute(
            "INSERT INTO points(user_id, points, msgs, last) VALUES($1,$2,1,now()) "
            "ON CONFLICT(user_id) DO UPDATE SET "
            "points = points.points + $2, msgs = points.msgs + 1, last = now()",
            user_id, n,
        )
    except Exception as e:
        print(f"LỖI ADD_POINTS (fallback ram): {type(e).__name__}: {e}", flush=True)
        _mem[user_id] = _mem.get(user_id, 0) + n


async def get_points(user_id: int) -> int:
    if db_pool is None:
        return _mem.get(user_id, 0)
    await _ensure_schema()
    row = await db_pool.fetchrow("SELECT points FROM points WHERE user_id=$1", user_id)
    return row["points"] if row else 0


async def get_rank(user_id: int):
    if db_pool is None:
        return None
    await _ensure_schema()
    return await db_pool.fetchval(
        "SELECT COUNT(*)+1 FROM points WHERE points > "
        "(SELECT COALESCE(points,0) FROM points WHERE user_id=$1)",
        user_id,
    )


async def get_top(limit: int = 10):
    if db_pool is None:
        items = sorted(_mem.items(), key=lambda x: -x[1])[:limit]
        return [{"user_id": uid, "points": pts} for uid, pts in items]
    await _ensure_schema()
    return await db_pool.fetch(
        "SELECT user_id, points FROM points ORDER BY points DESC LIMIT $1", limit
    )
