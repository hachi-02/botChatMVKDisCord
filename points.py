import asyncio
import discord
from datetime import datetime
from zoneinfo import ZoneInfo

from pilow_image.bag_pilow import create_bag
from pilow_image.levelup_pilow import create_levelup_card
from pilow_image.daily_pilow import create_daily_card

from config import (
    POINT_COOLDOWN,
    POINTS_PER_MSG,
    GEM_PER_MSG,
    MORA_PER_MSG,
    POINTS_PER_LEVEL,
    DAILY_GEMS,
    DAILY_MORA,
)

from db import (
    add_rewards,
    get_gems,
    get_mora,
    get_rank,
    get_xp,
    claim_daily,
)


# ============================================================
# CONFIG
# ============================================================

cooldown = {}

EMBED_COLOR = 0x1ABC9C

LEVELUP_GIF = (
    "https://media.giphy.com/media/"
    "v1.Y2lkPWVjZjA1ZTQ3dzd6ZDF0ZnJ1aXRlMzc1ZzV2M29zdnVteGN2ODN3MXExZmszaDlwdyZlcD12MV9naWZzX3NlYXJjaCZjdD1n/"
    "sIYOpmEC16sWVQtOs3/giphy.gif"
)


# ============================================================
# XP BAR FOR EMBED
# ============================================================

def _bar(
    done,
    total=POINTS_PER_LEVEL,
    size=10,
):
    if total <= 0:
        return "▱" * size

    filled = round(
        done / total * size
    )

    filled = max(
        0,
        min(
            filled,
            size,
        ),
    )

    return (
        "▰" * filled
        + "▱" * (size - filled)
    )


# ============================================================
# RANK COLOR
# ============================================================

def _rank_color(rank):
    return {
        1: 0xFFD700,
        2: 0xC0C0C0,
        3: 0xCD7F32,
    }.get(
        rank,
        EMBED_COLOR,
    )


# ============================================================
# BOT AUTHOR
# ============================================================

def _author(embed, bot):
    if bot.user:
        embed.set_author(
            name="Chị Cá 🐟",
            icon_url=bot.user.display_avatar.url,
        )


# ============================================================
# AWARD MESSAGE XP
# ============================================================

async def _award_and_notify(
    uid,
    author,
    channel,
    bot,
):
    old_xp = await get_xp(uid)

    old_lvl = (
        old_xp // POINTS_PER_LEVEL
        + 1
    )

    await add_rewards(
        uid,
        GEM_PER_MSG,
        MORA_PER_MSG,
        POINTS_PER_MSG,
    )

    xp = await get_xp(uid)

    new_lvl = (
        xp // POINTS_PER_LEVEL
        + 1
    )

    # ========================================================
    # LEVEL UP
    # ========================================================

    if new_lvl > old_lvl:
        prog = (
            xp % POINTS_PER_LEVEL
        )

        # ====================================================
        # PILLOW (phong cách giống bag / pvp)
        # ====================================================

        image = await create_levelup_card(
            author=author,
            level=new_lvl,
            xp=xp,
            prog=prog,
            points_per_level=POINTS_PER_LEVEL,
        )

        file = discord.File(
            image,
            filename="levelup.png",
        )

        # ====================================================
        # EMBED
        # ====================================================

        e = discord.Embed(
            title=(
                f"🎉 {author.display_name} "
                f"lên cấp {new_lvl}!"
            ),
            description=(
                f"{author.mention} "
                f"vừa đạt **Level {new_lvl}** 🐟"
            ),
            color=0xFFD700,
        )

        _author(
            e,
            bot,
        )

        e.set_image(
            url="attachment://levelup.png"
        )

        await channel.send(
            embed=e,
            file=file,
        )


# ============================================================
# MESSAGE XP COOLDOWN
# ============================================================

async def maybe_award_points(
    message,
    bot,
):
    if (
        message.author.bot
        or not message.guild
    ):
        return

    uid = message.author.id

    now = datetime.now(
        ZoneInfo(
            "Asia/Ho_Chi_Minh"
        )
    )

    last = cooldown.get(uid)

    if (
        last is None
        or (
            now - last
        ).total_seconds()
        >= POINT_COOLDOWN
    ) and len(
        message.content.strip()
    ) >= 5:

        cooldown[uid] = now

        asyncio.create_task(
            _award_and_notify(
                uid,
                message.author,
                message.channel,
                bot,
            )
        )


# ============================================================
# BAG / INVENTORY
# ============================================================

async def handle_assets(
    message,
    bot,
):
    # ========================================================
    # TARGET
    # ========================================================

    target = (
        message.mentions[0]
        if message.mentions
        else message.author
    )

    # ========================================================
    # GET DATA FROM DATABASE
    # ========================================================

    pts = await get_gems(
        target.id
    )

    mora = await get_mora(
        target.id
    )

    rank = await get_rank(
        target.id
    )

    xp = await get_xp(
        target.id
    )

    lvl = (
        xp // POINTS_PER_LEVEL
        + 1
    )

    # ========================================================
    # DEBUG
    # ========================================================

    print(
        "[BAG DATA]",
        f"user={target.display_name}",
        f"id={target.id}",
        f"gems={pts}",
        f"mora={mora}",
        f"rank={rank}",
        f"xp={xp}",
        f"level={lvl}",
    )

    # ========================================================
    # PILLOW
    #
    # Pillow chỉ render:
    # 1. XP
    # 2. Nguyên thạch
    # 3. Mora
    #
    # Không avatar
    # Không username
    # Không background
    # ========================================================

    image = await create_bag(
        target=target,
        gems=pts,
        mora=mora,
        rank=rank,
        level=lvl,
        xp=xp,
        points_per_level=POINTS_PER_LEVEL,
    )

    print(
        "[BAG PILLOW]",
        f"gems={pts}",
        f"mora={mora}",
        f"rank={rank}",
        f"level={lvl}",
        f"xp={xp}",
    )

    # ========================================================
    # DISCORD FILE
    # ========================================================

    file = discord.File(
        image,
        filename="bag.png",
    )

    # ========================================================
    # EMBED
    #
    # Không avatar bot
    # Không Chị Cá 🐟
    # Có avatar NGƯỜI CHƠI
    # ========================================================

    embed = discord.Embed(
        title="🎒 TÚI ĐỒ",
        color=_rank_color(rank),
    )

    # ========================================================
    # PLAYER INFO
    # ========================================================

    embed.add_field(
        name="Người chơi",
        value=(
            f"Tên: **{target.display_name}**\n"
            f"Rank: **{rank}**\n"
            f"Level: **{lvl}**"
        ),
        inline=True,
    )

    # ========================================================
    # PLAYER AVATAR
    # ========================================================

    embed.set_thumbnail(
        url=target.display_avatar.url
    )

    # ========================================================
    # PILLOW IMAGE
    # ========================================================

    embed.set_image(
        url="attachment://bag.png"
    )

    # ========================================================
    # FOOTER
    # ========================================================

    icon = None

    if (
        message.guild
        and message.guild.icon
    ):
        icon = message.guild.icon.url

    embed.set_footer(
        text=(
            "Mỗi tin nhắn +5 Nguyên Thạch "
            "+500 Mora +10 XP / 30s"
        ),
        icon_url=icon,
    )

    # ========================================================
    # SEND
    # ========================================================

    await message.channel.send(
        embed=embed,
        file=file,
        reference=message,
        mention_author=False,
    )


# ============================================================
# DAILY
# ============================================================

async def handle_daily(
    message,
    bot,
):
    uid = message.author.id

    ok = await claim_daily(
        uid,
        DAILY_GEMS,
        DAILY_MORA,
    )

    # ========================================================
    # ALREADY CLAIMED
    # ========================================================

    if not ok:
        pts = await get_gems(
            uid
        )

        mora = await get_mora(
            uid
        )

        image = await create_daily_card(
            author=message.author,
            gems=pts,
            mora=mora,
            reward_gems=0,
            reward_mora=0,
        )

        file = discord.File(
            image,
            filename="daily.png",
        )

        e = discord.Embed(
            title="📅 Điểm danh",
            description=(
                f"{message.author.mention} "
                "hôm nay đã điểm danh rồi, "
                "mai quay lại nhé! 🐟"
            ),
            color=EMBED_COLOR,
        )

        e.set_image(
            url="attachment://daily.png"
        )

        await message.channel.send(
            embed=e,
            file=file,
            reference=message,
            mention_author=False,
        )

        return

    # ========================================================
    # SUCCESS
    # ========================================================

    pts = await get_gems(
        uid
    )

    mora = await get_mora(
        uid
    )

    image = await create_daily_card(
        author=message.author,
        gems=pts,
        mora=mora,
        reward_gems=DAILY_GEMS,
        reward_mora=DAILY_MORA,
    )

    file = discord.File(
        image,
        filename="daily.png",
    )

    e = discord.Embed(
        title="📅 Điểm danh thành công!",
        description=(
            f"{message.author.mention} "
            f"nhận được **+{DAILY_GEMS} 💠** "
            f"và **+{DAILY_MORA} 🪙** 🎉\n"
            "Quay lại vào ngày mai để nhận tiếp nhé!"
        ),
        color=EMBED_COLOR,
    )

    e.set_image(
        url="attachment://daily.png"
    )

    await message.channel.send(
        embed=e,
        file=file,
        reference=message,
        mention_author=False,
    )