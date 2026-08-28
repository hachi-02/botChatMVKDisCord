from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

from config import DATABASE_URL, POINTS_PER_LEVEL

db_pool = None
_schema_ready = False
_no_db_warned = False

SCHEMA_SQL = (
    "CREATE TABLE IF NOT EXISTS points ("
    " user_id BIGINT PRIMARY KEY,"
    " points  INTEGER NOT NULL DEFAULT 0,"
    " msgs    INTEGER NOT NULL DEFAULT 0,"
    " last    TIMESTAMP);"
)

GACHA_SCHEMA_SQL = (
    "CREATE TABLE IF NOT EXISTS gacha_state ("
    " user_id BIGINT PRIMARY KEY,"
    " pity5 INT NOT NULL DEFAULT 0,"
    " pity4 INT NOT NULL DEFAULT 0,"
    " guarantee5 BOOLEAN NOT NULL DEFAULT FALSE);",
    "CREATE TABLE IF NOT EXISTS gacha_cards ("
    " user_id BIGINT,"
    " char_key TEXT,"
    " rarity TEXT,"
    " dup_count INT NOT NULL DEFAULT 1,"
    " first_at TIMESTAMPTZ DEFAULT now(),"
    " PRIMARY KEY (user_id, char_key));",
)

PVP_SCHEMA_SQL = (
    "CREATE TABLE IF NOT EXISTS pvp_rank ("
    " user_id BIGINT PRIMARY KEY,"
    " rating INTEGER NOT NULL DEFAULT 1000,"
    " wins INTEGER NOT NULL DEFAULT 0,"
    " losses INTEGER NOT NULL DEFAULT 0,"
    " last TIMESTAMPTZ);",
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
        for s in GACHA_SCHEMA_SQL:
            await conn.execute(s)
        for s in PVP_SCHEMA_SQL:
            await conn.execute(s)
        await conn.execute(
            "ALTER TABLE points DROP COLUMN IF EXISTS max_level"
        )
        await conn.execute(
            "ALTER TABLE points ADD COLUMN IF NOT EXISTS total_xp INTEGER NOT NULL DEFAULT 0"
        )
        await conn.execute(
            "UPDATE points SET total_xp = GREATEST(total_xp, points)"
        )
    _schema_ready = True


async def init_db():
    global db_pool
    if not DATABASE_URL:
        print("DATABASE_URL chưa cấu hình - points sẽ KHÔNG được lưu (không có RAM fallback).", flush=True)
        return
    import asyncpg

    dsn = _clean_dsn(DATABASE_URL)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=5, statement_cache_size=0)
    async with pool.acquire() as conn:
        await conn.execute(SCHEMA_SQL)
        for s in GACHA_SCHEMA_SQL:
            await conn.execute(s)
        for s in PVP_SCHEMA_SQL:
            await conn.execute(s)
    db_pool = pool
    _schema_ready = True
    print("Đã kết nối DB points thành công 🐟", flush=True)


async def add_points(user_id: int, n: int):
    global _no_db_warned
    if db_pool is None:
        if not _no_db_warned:
            print("WARN: db_pool is None - bỏ qua ghi điểm (chưa kết nối DB, không có RAM fallback).", flush=True)
            _no_db_warned = True
        return
    try:
        await _ensure_schema()
        await db_pool.execute(
            "INSERT INTO points(user_id, points, total_xp, msgs, last) VALUES($1,$2,$2,1,now()) "
            "ON CONFLICT(user_id) DO UPDATE SET "
            "points = points.points + $2, total_xp = points.total_xp + $2, "
            "msgs = points.msgs + 1, last = now()",
            user_id, n,
        )
    except Exception as e:
        print(f"LỖI ADD_POINTS: {type(e).__name__}: {e}", flush=True)


async def get_points(user_id: int) -> int:
    if db_pool is None:
        return 0
    await _ensure_schema()
    row = await db_pool.fetchrow("SELECT points FROM points WHERE user_id=$1", user_id)
    return row["points"] if row else 0


async def get_level(user_id: int) -> int:
    if db_pool is None:
        return 1
    await _ensure_schema()
    row = await db_pool.fetchrow("SELECT total_xp FROM points WHERE user_id=$1", user_id)
    return (row["total_xp"] // POINTS_PER_LEVEL) + 1 if row else 1


async def get_xp(user_id: int) -> int:
    if db_pool is None:
        return 0
    await _ensure_schema()
    row = await db_pool.fetchrow("SELECT total_xp FROM points WHERE user_id=$1", user_id)
    return row["total_xp"] if row else 0


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
        return []
    await _ensure_schema()
    return await db_pool.fetch(
        "SELECT user_id, points FROM points ORDER BY points DESC LIMIT $1", limit
    )


async def spend_points(user_id: int, n: int) -> bool:
    global _no_db_warned
    if db_pool is None:
        if not _no_db_warned:
            print("WARN: db_pool is None - bỏ qua trừ điểm (không có RAM fallback).", flush=True)
            _no_db_warned = True
        return False
    try:
        await _ensure_schema()
        row = await db_pool.fetchrow("SELECT points FROM points WHERE user_id=$1", user_id)
        cur = row["points"] if row else 0
        if cur < n:
            return False
        await db_pool.execute(
            "UPDATE points SET points = points - $2 WHERE user_id=$1", user_id, n
        )
        return True
    except Exception as e:
        print(f"LỖI SPEND_POINTS: {type(e).__name__}: {e}", flush=True)
        return False


async def get_state(user_id: int):
    if db_pool is None:
        return {"pity5": 0, "pity4": 0, "guarantee5": False}
    await _ensure_schema()
    row = await db_pool.fetchrow(
        "SELECT pity5, pity4, guarantee5 FROM gacha_state WHERE user_id=$1", user_id
    )
    if row is None:
        return {"pity5": 0, "pity4": 0, "guarantee5": False}
    return {
        "pity5": row["pity5"],
        "pity4": row["pity4"],
        "guarantee5": row["guarantee5"],
    }


async def set_state(user_id: int, pity5: int, pity4: int, guarantee5: bool):
    if db_pool is None:
        return
    try:
        await _ensure_schema()
        await db_pool.execute(
            "INSERT INTO gacha_state(user_id, pity5, pity4, guarantee5) VALUES($1,$2,$3,$4) "
            "ON CONFLICT(user_id) DO UPDATE SET pity5=$2, pity4=$3, guarantee5=$4",
            user_id, pity5, pity4, guarantee5,
        )
    except Exception as e:
        print(f"LỖI SET_STATE: {type(e).__name__}: {e}", flush=True)


async def add_card(user_id: int, char_key: str, rarity: str):
    if db_pool is None:
        return
    try:
        await _ensure_schema()
        await db_pool.execute(
            "INSERT INTO gacha_cards(user_id, char_key, rarity, dup_count, first_at) "
            "VALUES($1,$2,$3,1,now()) "
            "ON CONFLICT(user_id, char_key) DO UPDATE SET dup_count = gacha_cards.dup_count + 1",
            user_id, char_key, rarity,
        )
    except Exception as e:
        print(f"LỖI ADD_CARD: {type(e).__name__}: {e}", flush=True)


async def get_collection(user_id: int):
    if db_pool is None:
        return []
    await _ensure_schema()
    return await db_pool.fetch(
        "SELECT char_key, rarity, dup_count FROM gacha_cards WHERE user_id=$1 "
        "ORDER BY rarity, char_key",
        user_id,
    )


async def get_pvp_rating(user_id: int):
    default = {"rating": 1000, "wins": 0, "losses": 0}
    if db_pool is None:
        return default
    await _ensure_schema()
    row = await db_pool.fetchrow(
        "SELECT rating, wins, losses FROM pvp_rank WHERE user_id=$1", user_id
    )
    if row is None:
        return default
    return {"rating": row["rating"], "wins": row["wins"], "losses": row["losses"]}


async def get_pvp_top(limit: int = 10):
    if db_pool is None:
        return []
    await _ensure_schema()
    return await db_pool.fetch(
        "SELECT user_id, rating, wins, losses FROM pvp_rank "
        "ORDER BY rating DESC LIMIT $1",
        limit,
    )


async def update_pvp_result(
    winner_id: int, loser_id: int,
    new_winner_rating: int, new_loser_rating: int,
    draw: bool = False,
):
    if db_pool is None:
        return
    try:
        await _ensure_schema()
        if draw:
            await db_pool.execute(
                "INSERT INTO pvp_rank(user_id, rating, wins, losses, last) "
                "VALUES($1,$2,0,0,now()) "
                "ON CONFLICT(user_id) DO UPDATE SET rating=$2, last=now()",
                winner_id, new_winner_rating,
            )
            await db_pool.execute(
                "INSERT INTO pvp_rank(user_id, rating, wins, losses, last) "
                "VALUES($1,$2,0,0,now()) "
                "ON CONFLICT(user_id) DO UPDATE SET rating=$2, last=now()",
                loser_id, new_loser_rating,
            )
            return
        await db_pool.execute(
            "INSERT INTO pvp_rank(user_id, rating, wins, losses, last) "
            "VALUES($1,$2,1,0,now()) "
            "ON CONFLICT(user_id) DO UPDATE SET rating=$2, wins=pvp_rank.wins+1, last=now()",
            winner_id, new_winner_rating,
        )
        await db_pool.execute(
            "INSERT INTO pvp_rank(user_id, rating, wins, losses, last) "
            "VALUES($1,$2,0,1,now()) "
            "ON CONFLICT(user_id) DO UPDATE SET rating=$2, losses=pvp_rank.losses+1, last=now()",
            loser_id, new_loser_rating,
        )
    except Exception as e:
        print(f"LỖI UPDATE_PVP_RESULT: {type(e).__name__}: {e}", flush=True)

