import asyncio
import discord
from datetime import datetime
from zoneinfo import ZoneInfo
from pilow_image.bag_pilow import create_bag

from config import POINT_COOLDOWN, POINTS_PER_MSG, GEM_PER_MSG, MORA_PER_MSG, POINTS_PER_LEVEL, DAILY_GEMS, DAILY_MORA
from db import add_rewards, get_gems, get_mora, get_rank, get_xp, claim_daily

cooldown = {}
EMBED_COLOR = 0x1ABC9C
LEVELUP_GIF = "https://media.giphy.com/media/v1.Y2lkPWVjZjA1ZTQ3dzd6ZDF0ZnJ1aXRlMzc1ZzV2M29zdnVteGN2ODN3MXExZmszaDlwdyZlcD12MV9naWZzX3NlYXJjaCZjdD1n/sIYOpmEC16sWVQtOs3/giphy.gif"


def _bar(done, total=POINTS_PER_LEVEL, size=10):
    filled = round(done / total * size)
    return "▰" * filled + "▱" * (size - filled)


def _rank_color(rank):
    return {1: 0xFFD700, 2: 0xC0C0C0, 3: 0xCD7F32}.get(rank, EMBED_COLOR)


def _author(embed, bot):
    if bot.user:
        embed.set_author(name="Chị Cá 🐟", icon_url=bot.user.display_avatar.url)


async def _award_and_notify(uid, author, channel, bot):
    old = await get_gems(uid)
    old_xp = await get_xp(uid)
    old_lvl = old_xp // POINTS_PER_LEVEL + 1
    await add_rewards(uid, GEM_PER_MSG, MORA_PER_MSG, POINTS_PER_MSG)
    new = await get_gems(uid)
    xp = await get_xp(uid)
    new_lvl = xp // POINTS_PER_LEVEL + 1
    if new_lvl > old_lvl:
        prog = xp % POINTS_PER_LEVEL
        e = discord.Embed(
            title=f"🎉 {author.display_name} lên cấp {new_lvl}!",
            description=f"{author.mention} vừa đạt **{new}💠** 🐟",
            color=0xFFD700,
        )
        _author(e, bot)
        e.add_field(name="Cấp", value=f"**{new_lvl}**", inline=True)
        e.add_field(
            name="Tiến độ",
            value=f"[{_bar(prog)}] {prog}/{POINTS_PER_LEVEL}đ",
            inline=True,
        )
        await channel.send(embed=e)


async def maybe_award_points(message, bot):
    if message.author.bot or not message.guild:
        return
    uid = message.author.id
    now = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))
    last = cooldown.get(uid)
    if (last is None or (now - last).total_seconds() >= POINT_COOLDOWN) \
            and len(message.content.strip()) >= 5:
        cooldown[uid] = now
        asyncio.create_task(_award_and_notify(uid, message.author, message.channel, bot))


async def handle_assets(message, bot):
    target = message.mentions[0] if message.mentions else message.author

    pts = await get_gems(target.id)
    mora = await get_mora(target.id)
    rank = await get_rank(target.id)
    xp = await get_xp(target.id)

    lvl = xp // POINTS_PER_LEVEL + 1

    image = await create_bag(
        target=target,
        gems=pts,
        mora=mora,
        rank=rank,
        level=lvl,
        xp=xp,
        points_per_level=POINTS_PER_LEVEL,
    )

    await message.channel.send(
        file=discord.File(
            image,
            filename="bag.png",
        ),
        reference=message,
        mention_author=False,
    )

async def handle_daily(message, bot):
    uid = message.author.id
    ok = await claim_daily(uid, DAILY_GEMS, DAILY_MORA)
    if not ok:
        pts = await get_gems(uid)
        mora = await get_mora(uid)
        e = discord.Embed(
            title="📅 Điểm danh",
            description=f"{message.author.mention} hôm nay đã điểm danh rồi, mai quay lại nhé! 🐟",
            color=EMBED_COLOR,
        )
        _author(e, bot)
        e.add_field(name="Nguyên thạch", value=f"**{pts}💠**", inline=True)
        e.add_field(name="Mora", value=f"**{mora}🪙**", inline=True)
        await message.channel.send(embed=e, reference=message, mention_author=False)
        return
    pts = await get_gems(uid)
    mora = await get_mora(uid)
    e = discord.Embed(
        title="📅 Điểm danh thành công!",
        description=f"{message.author.mention} nhận được **+{DAILY_GEMS}💠** và **+{DAILY_MORA}🪙** 🎉\nQuay lại vào ngày mai để nhận tiếp nhé!",
        color=EMBED_COLOR,
    )
    _author(e, bot)
    e.add_field(name="Nguyên thạch", value=f"**{pts}❖**", inline=True)
    e.add_field(name="Mora", value=f"**{mora}🪙**", inline=True)
    await message.channel.send(embed=e, reference=message, mention_author=False)
