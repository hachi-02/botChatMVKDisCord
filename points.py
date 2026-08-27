import asyncio
from datetime import datetime, ZoneInfo

from config import POINT_COOLDOWN, POINTS_PER_MSG, POINTS_PER_LEVEL
from db import add_points, get_points, get_rank, get_top

cooldown = {}


async def maybe_award_points(message):
    if message.author.bot or not message.guild:
        return
    uid = message.author.id
    now = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))
    last = cooldown.get(uid)
    if (last is None or (now - last).total_seconds() >= POINT_COOLDOWN) \
            and len(message.content.strip()) >= 5:
        cooldown[uid] = now
        asyncio.create_task(add_points(uid, POINTS_PER_MSG))


async def handle_points(message):
    content_lower = message.content.lower()
    if any(k in content_lower for k in ("top", "xếp hạng", "leaderboard")):
        rows = await get_top(10)
        if not rows:
            await message.channel.send("Chưa có ai tích điểm cả 🐟", reference=message)
            return
        lines = []
        for i, r in enumerate(rows, 1):
            uid = r["user_id"]
            pts = r["points"]
            user = message.client.get_user(uid) or await message.client.fetch_user(uid)
            name = user.display_name if user else f"user {uid}"
            lines.append(f"{i}. {name}: {pts}đ")
        await message.channel.send("🏆 Top 10:\n" + "\n".join(lines), reference=message)
        return

    target = message.mentions[0] if message.mentions else message.author
    pts = await get_points(target.id)
    rank = await get_rank(target.id)
    lvl = pts // POINTS_PER_LEVEL + 1
    await message.channel.send(
        f"🐟 {target.display_name}: **{pts}đ** | Cấp {lvl}"
        + (f" | Hạng {rank}" if rank else ""),
        reference=message,
    )
