from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode
from config import DATABASE_URL, POINTS_PER_LEVEL

db_pool = None
_schema_ready = False
_no_db_warned = False

# Gom toàn bộ DDL vào danh sách các câu lệnh độc lập (list of strings)
SCHEMA_STATEMENTS = [
    # Bảng points
    """
    CREATE TABLE IF NOT EXISTS points (
        user_id BIGINT PRIMARY KEY,
        points INTEGER NOT NULL DEFAULT 0,
        mora INTEGER NOT NULL DEFAULT 0,
        total_xp INTEGER NOT NULL DEFAULT 0,
        msgs INTEGER NOT NULL DEFAULT 0,
        last TIMESTAMP,
        last_checkin DATE
    );
    """,
    # Bảng Gacha
    """
    CREATE TABLE IF NOT EXISTS gacha_state (
        user_id BIGINT PRIMARY KEY,
        pity5 INT NOT NULL DEFAULT 0,
        pity4 INT NOT NULL DEFAULT 0,
        guarantee5 BOOLEAN NOT NULL DEFAULT FALSE
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS gacha_cards (
        user_id BIGINT,
        char_key TEXT,
        rarity TEXT,
        dup_count INT NOT NULL DEFAULT 1,
        lvl INT NOT NULL DEFAULT 1,
        first_at TIMESTAMPTZ DEFAULT now(),
        PRIMARY KEY (user_id, char_key)
    );
    """,
    # Bảng PvP
    """
    CREATE TABLE IF NOT EXISTS pvp_rank (
        user_id BIGINT PRIMARY KEY,
        rating INTEGER NOT NULL DEFAULT 1000,
        wins INTEGER NOT NULL DEFAULT 0,
        losses INTEGER NOT NULL DEFAULT 0,
        last TIMESTAMPTZ
    );
    """,
    # Bảng Report/Log
    """
    CREATE TABLE IF NOT EXISTS msg_log (
        id BIGSERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL,
        channel_id BIGINT NOT NULL,
        guild_id BIGINT NOT NULL,
        at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_msg_log_week ON msg_log (at, guild_id);",
    """
    CREATE TABLE IF NOT EXISTS xp_snapshot (
        guild_id BIGINT NOT NULL,
        user_id BIGINT NOT NULL,
        xp INTEGER NOT NULL,
        at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (guild_id, user_id)
    );
    """,
    # Bảng Nhà tù công ích (Jail System)
    """
    CREATE TABLE IF NOT EXISTS jail_state (
        user_id BIGINT PRIMARY KEY,
        target_count INT NOT NULL,
        done_count INT NOT NULL DEFAULT 0,
        original_roles TEXT NOT NULL,
        current_sentence TEXT,
        jailed_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """,
    # Migration Schema (Nâng cấp cột an toàn)
    "ALTER TABLE gacha_cards ADD COLUMN IF NOT EXISTS lvl INT NOT NULL DEFAULT 1;",
    "ALTER TABLE points DROP COLUMN IF EXISTS max_level;",
    "ALTER TABLE points ADD COLUMN IF NOT EXISTS mora INTEGER NOT NULL DEFAULT 0;",
    "ALTER TABLE points ADD COLUMN IF NOT EXISTS total_xp INTEGER NOT NULL DEFAULT 0;",
    "ALTER TABLE points ADD COLUMN IF NOT EXISTS last_checkin DATE;",
    "UPDATE points SET total_xp = GREATEST(total_xp, points);"
]


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
        async with conn.transaction():
            for stmt in SCHEMA_STATEMENTS:
                await conn.execute(stmt)
    _schema_ready = True


async def init_db():
    global db_pool
    if not DATABASE_URL:
        print("DATABASE_URL chưa cấu hình - points sẽ KHÔNG được lưu (không có RAM fallback).", flush=True)
        return
    import asyncpg

    dsn = _clean_dsn(DATABASE_URL)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=5, statement_cache_size=0)
    db_pool = pool
    await _ensure_schema()
    print("Đã kết nối DB points thành công 🐟", flush=True)


async def add_rewards(user_id: int, gems: int, mora: int, xp: int):
    global _no_db_warned
    if db_pool is None:
        if not _no_db_warned:
            print("WARN: db_pool is None - bỏ qua ghi thưởng.", flush=True)
            _no_db_warned = True
        return
    try:
        await _ensure_schema()
        await db_pool.execute(
            """
            INSERT INTO points(user_id, points, mora, total_xp, msgs, last)
            VALUES($1, $2, $3, $4, 1, now())
            ON CONFLICT(user_id) DO UPDATE SET
                points = points.points + $2,
                mora = points.mora + $3,
                total_xp = points.total_xp + $4,
                msgs = points.msgs + 1,
                last = now()
            """,
            user_id, gems, mora, xp,
        )
    except Exception as e:
        print(f"LỖI ADD_REWARDS: {type(e).__name__}: {e}", flush=True)


async def get_gems(user_id: int) -> int:
    if db_pool is None:
        return 0
    await _ensure_schema()
    row = await db_pool.fetchrow("SELECT points FROM points WHERE user_id=$1", user_id)
    return row["points"] if row else 0


async def get_mora(user_id: int) -> int:
    if db_pool is None:
        return 0
    await _ensure_schema()
    row = await db_pool.fetchrow("SELECT mora FROM points WHERE user_id=$1", user_id)
    return row["mora"] if row else 0


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
        """
        SELECT COUNT(*)+1 FROM points 
        WHERE points > (SELECT COALESCE(points, 0) FROM points WHERE user_id=$1)
        """,
        user_id,
    )


async def get_top(limit: int = 10):
    if db_pool is None:
        return []
    await _ensure_schema()
    return await db_pool.fetch(
        "SELECT user_id, points FROM points ORDER BY points DESC LIMIT $1", limit
    )


async def spend_gems(user_id: int, n: int) -> bool:
    global _no_db_warned
    if db_pool is None:
        if not _no_db_warned:
            print("WARN: db_pool is None - bỏ qua trừ nguyên thạch.", flush=True)
            _no_db_warned = True
        return False
    try:
        await _ensure_schema()
        res = await db_pool.execute(
            "UPDATE points SET points = points - $2 WHERE user_id=$1 AND points >= $2",
            user_id, n
        )
        return res == "UPDATE 1"
    except Exception as e:
        print(f"LỖI SPEND_GEMS: {type(e).__name__}: {e}", flush=True)
        return False


async def spend_mora(user_id: int, n: int) -> bool:
    global _no_db_warned
    if db_pool is None:
        if not _no_db_warned:
            print("WARN: db_pool is None - bỏ qua trừ mora.", flush=True)
            _no_db_warned = True
        return False
    try:
        await _ensure_schema()
        res = await db_pool.execute(
            "UPDATE points SET mora = mora - $2 WHERE user_id=$1 AND mora >= $2",
            user_id, n
        )
        return res == "UPDATE 1"
    except Exception as e:
        print(f"LỖI SPEND_MORA: {type(e).__name__}: {e}", flush=True)
        return False


async def get_state(user_id: int):
    default = {"pity5": 0, "pity4": 0, "guarantee5": False}
    if db_pool is None:
        return default
    await _ensure_schema()
    row = await db_pool.fetchrow(
        "SELECT pity5, pity4, guarantee5 FROM gacha_state WHERE user_id=$1", user_id
    )
    if row is None:
        return default
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
            """
            INSERT INTO gacha_state(user_id, pity5, pity4, guarantee5) VALUES($1,$2,$3,$4)
            ON CONFLICT(user_id) DO UPDATE SET pity5=$2, pity4=$3, guarantee5=$4
            """,
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
            """
            INSERT INTO gacha_cards(user_id, char_key, rarity, dup_count, first_at)
            VALUES($1, $2, $3, 1, now())
            ON CONFLICT(user_id, char_key) DO UPDATE SET dup_count = gacha_cards.dup_count + 1
            """,
            user_id, char_key, rarity,
        )
    except Exception as e:
        print(f"LỖI ADD_CARD: {type(e).__name__}: {e}", flush=True)


async def get_collection(user_id: int):
    if db_pool is None:
        return []
    await _ensure_schema()
    return await db_pool.fetch(
        """
        SELECT char_key, rarity, dup_count, lvl FROM gacha_cards 
        WHERE user_id=$1 ORDER BY rarity DESC, char_key ASC
        """,
        user_id,
    )


async def get_char_level(user_id: int, char_key: str) -> int:
    if db_pool is None:
        return 1
    await _ensure_schema()
    row = await db_pool.fetchrow(
        "SELECT lvl FROM gacha_cards WHERE user_id=$1 AND char_key=$2",
        user_id, char_key,
    )
    return row["lvl"] if row else 1


async def set_char_level(user_id: int, char_key: str, lvl: int):
    if db_pool is None:
        return
    try:
        await _ensure_schema()
        await db_pool.execute(
            "UPDATE gacha_cards SET lvl=$3 WHERE user_id=$1 AND char_key=$2",
            user_id, char_key, lvl,
        )
    except Exception as e:
        print(f"LỖI SET_CHAR_LEVEL: {type(e).__name__}: {e}", flush=True)


async def get_pvp_rating(user_id: int):
    default = {"rating": 1000, "wins": 0, "losses": 0}
    if db_pool is None:
        return default
    await _ensure_schema()
    row = await db_pool.fetchrow(
        "SELECT rating, wins, losses FROM pvp_rank WHERE user_id=$1", user_id
    )
    return {"rating": row["rating"], "wins": row["wins"], "losses": row["losses"]} if row else default


async def get_pvp_top(limit: int = 10):
    if db_pool is None:
        return []
    await _ensure_schema()
    return await db_pool.fetch(
        "SELECT user_id, rating, wins, losses FROM pvp_rank ORDER BY rating DESC LIMIT $1",
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
                """
                INSERT INTO pvp_rank(user_id, rating, wins, losses, last) VALUES($1, $2, 0, 0, now())
                ON CONFLICT(user_id) DO UPDATE SET rating=$2, last=now()
                """,
                winner_id, new_winner_rating,
            )
            await db_pool.execute(
                """
                INSERT INTO pvp_rank(user_id, rating, wins, losses, last) VALUES($1, $2, 0, 0, now())
                ON CONFLICT(user_id) DO UPDATE SET rating=$2, last=now()
                """,
                loser_id, new_loser_rating,
            )
            return

        await db_pool.execute(
            """
            INSERT INTO pvp_rank(user_id, rating, wins, losses, last) VALUES($1, $2, 1, 0, now())
            ON CONFLICT(user_id) DO UPDATE SET rating=$2, wins=pvp_rank.wins+1, last=now()
            """,
            winner_id, new_winner_rating,
        )
        await db_pool.execute(
            """
            INSERT INTO pvp_rank(user_id, rating, wins, losses, last) VALUES($1, $2, 0, 1, now())
            ON CONFLICT(user_id) DO UPDATE SET rating=$2, losses=pvp_rank.losses+1, last=now()
            """,
            loser_id, new_loser_rating,
        )
    except Exception as e:
        print(f"LỖI UPDATE_PVP_RESULT: {type(e).__name__}: {e}", flush=True)


async def log_message(user_id: int, channel_id: int, guild_id: int):
    if db_pool is None:
        return
    try:
        await _ensure_schema()
        await db_pool.execute(
            "INSERT INTO msg_log(user_id, channel_id, guild_id, at) VALUES($1, $2, $3, now())",
            user_id, channel_id, guild_id,
        )
    except Exception as e:
        print(f"LỖI LOG_MESSAGE: {type(e).__name__}: {e}", flush=True)


async def cleanup_msg_log(days: int = 30):
    if db_pool is None:
        return
    try:
        await _ensure_schema()
        await db_pool.execute(
            "DELETE FROM msg_log WHERE at < now() - make_interval(days => $1)", days
        )
    except Exception as e:
        print(f"LỖI CLEANUP_MSG_LOG: {type(e).__name__}: {e}", flush=True)


async def get_week_top_msg(guild_id: int, start) -> dict:
    if db_pool is None:
        return None
    await _ensure_schema()
    row = await db_pool.fetchrow(
        """
        SELECT user_id, COUNT(*) AS cnt FROM msg_log
        WHERE guild_id=$1 AND at >= $2
        GROUP BY user_id ORDER BY cnt DESC LIMIT 1
        """,
        guild_id, start,
    )
    return {"user_id": row["user_id"], "count": row["cnt"]} if row else None


async def get_week_bottom_msg(guild_id: int, start) -> dict:
    if db_pool is None:
        return None
    await _ensure_schema()
    row = await db_pool.fetchrow(
        """
        SELECT user_id, COUNT(*) AS cnt FROM msg_log
        WHERE guild_id=$1 AND at >= $2
        GROUP BY user_id ORDER BY cnt ASC LIMIT 1
        """,
        guild_id, start,
    )
    return {"user_id": row["user_id"], "count": row["cnt"]} if row else None


async def get_week_top_channel(guild_id: int, start) -> dict:
    if db_pool is None:
        return None
    await _ensure_schema()
    row = await db_pool.fetchrow(
        """
        SELECT channel_id, COUNT(*) AS cnt FROM msg_log
        WHERE guild_id=$1 AND at >= $2
        GROUP BY channel_id ORDER BY cnt DESC LIMIT 1
        """,
        guild_id, start,
    )
    return {"channel_id": row["channel_id"], "count": row["cnt"]} if row else None


async def save_xp_snapshot(guild_id: int, xp_map: dict):
    if db_pool is None or not xp_map:
        return
    try:
        await _ensure_schema()
        args = [(guild_id, uid, xp) for uid, xp in xp_map.items()]
        async with db_pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("DELETE FROM xp_snapshot WHERE guild_id=$1", guild_id)
                await conn.executemany(
                    "INSERT INTO xp_snapshot(guild_id, user_id, xp, at) VALUES($1, $2, $3, now())",
                    args
                )
    except Exception as e:
        print(f"LỖI SAVE_XP_SNAPSHOT: {type(e).__name__}: {e}", flush=True)


async def get_xp_snapshot(guild_id: int) -> dict:
    if db_pool is None:
        return {}
    await _ensure_schema()
    rows = await db_pool.fetch(
        "SELECT user_id, xp FROM xp_snapshot WHERE guild_id=$1", guild_id
    )
    return {r["user_id"]: r["xp"] for r in rows}


async def get_all_xp(guild_id: int) -> dict:
    if db_pool is None:
        return {}
    await _ensure_schema()
    rows = await db_pool.fetch("SELECT user_id, total_xp FROM points")
    return {r["user_id"]: r["total_xp"] for r in rows}


async def claim_daily(user_id: int, gems: int, mora: int) -> bool:
    if db_pool is None:
        return False
    try:
        await _ensure_schema()
        result = await db_pool.fetchval(
            """
            INSERT INTO points(user_id, points, mora, last_checkin)
            VALUES($1, $2, $3, CURRENT_DATE)
            ON CONFLICT (user_id) DO UPDATE SET
                points = points.points + $2,
                mora = points.mora + $3,
                last_checkin = CURRENT_DATE
            WHERE points.last_checkin IS DISTINCT FROM CURRENT_DATE
            RETURNING user_id;
            """,
            user_id, gems, mora,
        )
        return result is not None
    except Exception as e:
        print(f"LỖI CLAIM_DAILY: {type(e).__name__}: {e}", flush=True)
        return False


# ==========================================
# CÁC HÀM XỬ LÝ NHÀ TÙ CÔNG ÍCH (JAIL SYSTEM)
# ==========================================

async def jail_user(user_id: int, target_count: int, original_roles: list[int]):
    """Đưa user vào tù và lưu lại danh sách role cũ."""
    if db_pool is None:
        return
    try:
        await _ensure_schema()
        roles_str = ",".join(map(str, original_roles))
        await db_pool.execute(
            """
            INSERT INTO jail_state(user_id, target_count, done_count, original_roles, jailed_at)
            VALUES($1, $2, 0, $3, now())
            ON CONFLICT (user_id) DO UPDATE SET
                target_count = $2,
                done_count = 0,
                original_roles = $3,
                current_sentence = NULL,
                jailed_at = now();
            """,
            user_id, target_count, roles_str
        )
    except Exception as e:
        print(f"LỖI JAIL_USER: {type(e).__name__}: {e}", flush=True)


async def unjail_user(user_id: int):
    """Xóa user khỏi bảng nhà tù."""
    if db_pool is None:
        return
    try:
        await _ensure_schema()
        await db_pool.execute("DELETE FROM jail_state WHERE user_id=$1", user_id)
    except Exception as e:
        print(f"LỖI UNJAIL_USER: {type(e).__name__}: {e}", flush=True)


async def get_jail_state(user_id: int):
    """Lấy thông tin tù nhân. Trả về dict hoặc None."""
    if db_pool is None:
        return None
    await _ensure_schema()
    row = await db_pool.fetchrow("SELECT * FROM jail_state WHERE user_id=$1", user_id)
    if not row:
        return None
    return {
        "user_id": row["user_id"],
        "target_count": row["target_count"],
        "done_count": row["done_count"],
        "original_roles": [int(r) for r in row["original_roles"].split(",") if r],
        "current_sentence": row["current_sentence"]
    }


async def set_jail_sentence(user_id: int, sentence: str):
    """Cập nhật câu chép phạt hiện tại cho tù nhân."""
    if db_pool is None:
        return
    try:
        await _ensure_schema()
        await db_pool.execute(
            "UPDATE jail_state SET current_sentence=$2 WHERE user_id=$1",
            user_id, sentence
        )
    except Exception as e:
        print(f"LỖI SET_JAIL_SENTENCE: {type(e).__name__}: {e}", flush=True)


async def increment_jail_done(user_id: int) -> dict:
    """Tăng số câu đã chép lên 1 và trả về state mới."""
    if db_pool is None:
        return None
    try:
        await _ensure_schema()
        row = await db_pool.fetchrow(
            """
            UPDATE jail_state 
            SET done_count = done_count + 1, current_sentence = NULL 
            WHERE user_id=$1 
            RETURNING user_id, target_count, done_count, original_roles;
            """,
            user_id
        )
        if not row:
            return None
        return {
            "user_id": row["user_id"],
            "target_count": row["target_count"],
            "done_count": row["done_count"],
            "original_roles": [int(r) for r in row["original_roles"].split(",") if r]
        }
    except Exception as e:
        print(f"LỖI INCREMENT_JAIL_DONE: {type(e).__name__}: {e}", flush=True)
        return None