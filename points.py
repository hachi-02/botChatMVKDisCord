import asyncio
import discord
from datetime import datetime
from zoneinfo import ZoneInfo

from config import POINT_COOLDOWN, POINTS_PER_MSG, POINTS_PER_LEVEL
from db import add_points, get_points, get_rank, get_top

cooldown = {}
EMBED_COLOR = 0x1ABC9C


def _bar(done, total=POINTS_PER_LEVEL, size=10):
    filled = round(done / total * size)
    return "▰" * filled + "▱" * (size - filled)


def _rank_color(rank):
    return {1: 0xFFD700, 2: 0xC0C0C0, 3: 0xCD7F32}.get(rank, EMBED_COLOR)


def _author(embed, bot):
    if bot.user:
        embed.set_author(name="Chị Cá 🐟", icon_url=bot.user.display_avatar.url)


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
        embed = discord.Embed(title="🏆 Top 10 Chị Cá", color=EMBED_COLOR)
        _author(embed, bot)
        if not rows:
            embed.description = "Hãy chat (tin nhắn ≥ 5 ký tự) để nhận điểm nhé! Mỗi tin ~30s được +1đ."
            embed.set_footer(text="Chưa có ai tích điểm • Tích điểm mỗi tin nhắn")
            await message.channel.send(embed=embed, reference=message)
            return
        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        total = 0
        for i, r in enumerate(rows, 1):
            uid = r["user_id"]
            pts = r["points"]
            total += pts
            user = message.guild.get_member(uid) if message.guild else None
            if user is None:
                user = bot.get_user(uid) or await bot.fetch_user(uid)
            name = user.display_name if user else f"user {uid}"
            lvl = pts // POINTS_PER_LEVEL + 1
            embed.add_field(
                name=f"{medals.get(i, f'#{i}')} {name}",
                value=f"**{pts}đ** • Cấp {lvl}",
                inline=True,
            )
        now = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).strftime("%H:%M %d/%m")
        embed.set_footer(text=f"📊 Tổng {total}đ • Cập nhật {now}")
        await message.channel.send(embed=embed, reference=message)
        return

    target = message.mentions[0] if message.mentions else message.author
    pts = await get_points(target.id)
    rank = await get_rank(target.id)
    lvl = pts // POINTS_PER_LEVEL + 1
    embed = discord.Embed(title=f"🐟 {target.display_name}", color=_rank_color(rank))
    _author(embed, bot)
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name="Điểm", value=f"**{pts}đ**", inline=True)
    embed.add_field(name="Cấp", value=f"**{lvl}**", inline=True)
    embed.add_field(name="Hạng", value=f"**{rank}**" if rank else "—", inline=True)
    embed.add_field(
        name="Tiến độ",
        value=f"Lên Cấp {lvl+1}: [{_bar(pts)}] {pts % POINTS_PER_LEVEL}/{POINTS_PER_LEVEL}đ",
        inline=False,
    )
    icon = message.guild.icon.url if (message.guild and message.guild.icon) else discord.Embed.Empty
    embed.set_footer(text="Tích điểm mỗi tin nhắn • +1đ / 30s", icon_url=icon)
    await message.channel.send(embed=embed, reference=message)
