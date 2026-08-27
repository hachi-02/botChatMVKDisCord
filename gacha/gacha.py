import asyncio
import random

import discord

from db import (
    get_points,
    spend_points,
    get_state,
    set_state,
    add_card,
    get_collection,
)
from .cards import CHARACTER_POOL, RARITY_COLOR, RARITY_LABEL

EMBED_COLOR = 0x1ABC9C

GACHA_COST = 50
GACHA_COST5 = 250
PITY_5_HARD = 90
PITY_5_SOFT = 74
PITY_4 = 10
RATE_5 = 0.006
RATE_50_50 = 0.5
SOFT_MAX_RATE = 0.33
GACHA_ROLL_GIF = "https://res.cloudinary.com/z2ffqaaf/image/upload/v1787830778/animationgacha_grcwt8.webp"

NAME_BY_KEY = {c["key"]: c["name"] for c in CHARACTER_POOL}


def _anim(url, w=300):
    return url.replace("/upload/", f"/upload/f_webp,w_{w}/", 1)


def _star_str(rarity):
    return "★★★★★" if rarity in ("5L", "5S") else "★★★★"


def _build_gacha_embeds(results, is_new_list):
    embeds = []
    for r, is_new in zip(results, is_new_list):
        e = discord.Embed(color=RARITY_COLOR.get(r["rarity"], EMBED_COLOR))
        e.set_thumbnail(url=_anim(r["url"], 80))
        stars = _star_str(r["rarity"])
        val = f"{stars}  ({RARITY_LABEL[r['rarity']]})"
        if is_new:
            val += "\n✨ **MỚI!**"
        e.add_field(name="\u200b", value="\u200b", inline=True)
        e.add_field(name=r["name"], value=val, inline=True)
        embeds.append(e)
    return embeds


def roll_one(state):
    state["pity5"] += 1
    state["pity4"] += 1
    if state["pity5"] >= PITY_5_HARD:
        is_5 = True
    elif state["pity5"] >= PITY_5_SOFT:
        p = RATE_5 + (state["pity5"] - PITY_5_SOFT) / (PITY_5_HARD - PITY_5_SOFT) * (SOFT_MAX_RATE - RATE_5)
        is_5 = random.random() < p
    else:
        is_5 = random.random() < RATE_5

    if is_5:
        if state["guarantee5"]:
            limited = True
            state["guarantee5"] = False
        else:
            limited = random.random() < RATE_50_50
            state["guarantee5"] = not limited
        rarity = "5L" if limited else "5S"
        state["pity5"] = 0
        state["pity4"] = 0
    else:
        rarity = "4"
        state["pity4"] = 0

    pool = [c for c in CHARACTER_POOL if c["rarity"] == rarity]
    return random.choice(pool)


async def handle_gacha(channel, author, bot, n):
    cost = GACHA_COST if n == 1 else GACHA_COST5
    uid = author.id
    pts = await get_points(uid)
    if pts < cost:
        await channel.send(
            f"{author.mention} chưa đủ điểm quay {n} lần (cần **{cost}đ**, em có **{pts}đ**). "
            f"Tích điểm mỗi tin nhắn nhé! 🐟"
        )
        return

    await spend_points(uid, cost)
    state = await get_state(uid)
    results = [roll_one(state) for _ in range(n)]
    await set_state(uid, state["pity5"], state["pity4"], state["guarantee5"])

    owned = {c["char_key"]: c["dup_count"] for c in await get_collection(uid)}
    local_seen = {}
    is_new_list = []
    for r in results:
        base = owned.get(r["key"], 0)
        seen = local_seen.get(r["key"], 0)
        is_new_list.append((base + seen) == 0)
        local_seen[r["key"]] = seen + 1

    roll = discord.Embed(title="🎰 Đang quay...", color=EMBED_COLOR)
    roll.set_image(url=GACHA_ROLL_GIF)
    msg = await channel.send(embed=roll)
    await asyncio.sleep(5.2)
    try:
        await msg.delete()
    except Exception:
        pass

    embeds = _build_gacha_embeds(results, is_new_list)
    await channel.send(
        content=f"🎴 Kết quả quay **{n} lần** của {author.mention}:",
        embeds=embeds,
    )
    for r in results:
        await add_card(uid, r["key"], r["rarity"])


async def handle_collection(channel, author, bot):
    uid = author.id
    rows = await get_collection(uid)
    if not rows:
        await channel.send(
            f"{author.mention} em chưa có thẻ nào. Quay thử `chị cá gacha` đi! 🎴"
        )
        return
    groups = {"5L": [], "5S": [], "4": []}
    for c in rows:
        groups.setdefault(c["rarity"], []).append(c)
    lines = []
    for rar in ("5L", "5S", "4"):
        for c in groups[rar]:
            lines.append(f"{RARITY_LABEL[rar]}: **{NAME_BY_KEY.get(c['char_key'], c['char_key'])}** x{c['dup_count']}")
    e = discord.Embed(title=f"🎴 Bộ sưu tập của {author.display_name}", color=EMBED_COLOR)
    e.description = "\n".join(lines) if lines else "Trống"
    total_cards = sum(c["dup_count"] for c in rows)
    e.set_footer(text=f"Tổng {len(rows)} loại • {total_cards} thẻ (tính cả dup)")
    await channel.send(embed=e)


class GachaView(discord.ui.View):
    def __init__(self, bot, author):
        super().__init__(timeout=180)
        self.bot = bot
        self.author = author

    async def interaction_check(self, interaction):
        return interaction.user.id == self.author.id

    @discord.ui.button(label="🎯 Quay 1 lần (50đ)", style=discord.ButtonStyle.primary)
    async def quay_1(self, interaction, button):
        await self._run(interaction, 1)

    @discord.ui.button(label="🎯 Quay 5 lần (250đ)", style=discord.ButtonStyle.success)
    async def quay_5(self, interaction, button):
        await self._run(interaction, 5)

    async def _run(self, interaction, n):
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)
        await handle_gacha(interaction.channel, interaction.user, self.bot, n)
