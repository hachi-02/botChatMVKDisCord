import asyncio
import discord
from datetime import datetime
from zoneinfo import ZoneInfo

from config import POINT_COOLDOWN, POINTS_PER_MSG, POINTS_PER_LEVEL
from db import add_points, get_points, get_rank, get_top

cooldown = {}
EMBED_COLOR = 0x1ABC9C



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


async def handle_points(message, bot):
    content_lower = message.content.lower()
    if any(k in content_lower for k in ("top", "xếp hạng", "leaderboard")):
        rows = await get_top(10)
        if not rows:
            embed = discord.Embed(
                title="🐟 Chưa có ai tích điểm",
                description="Hãy chat (tin nhắn ≥ 5 ký tự) để nhận điểm nhé! Mỗi tin ~30s được +1đ.",
                color=EMBED_COLOR,
            )
            await message.channel.send(embed=embed, reference=message)
            return
        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        lines = []
        for i, r in enumerate(rows, 1):
            uid = r["user_id"]
            pts = r["points"]
            user = message.guild.get_member(uid) if message.guild else None
            if user is None:
                user = bot.get_user(uid) or await bot.fetch_user(uid)
            name = user.display_name if user else f"user {uid}"
            lines.append(f"{medals.get(i, f'#{i}')} {name}: **{pts}đ**")
        now = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).strftime("%H:%M %d/%m")
        embed = discord.Embed(
            title="🏆 Top 10 Chị Cá",
            description="\n".join(lines),
            color=EMBED_COLOR,
        )
        embed.set_footer(text=f"Cập nhật {now}")
        await message.channel.send(embed=embed, reference=message)
        return

    target = message.mentions[0] if message.mentions else message.author
    pts = await get_points(target.id)
    rank = await get_rank(target.id)
    lvl = pts // POINTS_PER_LEVEL + 1
    embed = discord.Embed(
        title=f"🐟 {target.display_name}",
        color=EMBED_COLOR,
    )
    embed.add_field(name="Điểm", value=f"**{pts}đ**", inline=True)
    embed.add_field(name="Cấp", value=f"**{lvl}**", inline=True)
    embed.add_field(name="Hạng", value=f"**{rank}**" if rank else "—", inline=True)
    embed.set_footer(text="Tích điểm mỗi tin nhắn • +1đ / 30s")
    await message.channel.send(embed=embed, reference=message)
