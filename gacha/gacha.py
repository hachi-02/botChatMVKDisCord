import asyncio
import random

import discord

from db import (
    get_gems,
    spend_gems,
    get_state,
    set_state,
    add_card,
    get_collection,
)
from game.pvp.ui import is_in_pvp
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

GACHA_ROLL_GIF = (
    "https://res.cloudinary.com/z2ffqaaf/image/upload/"
    "v1787830778/animationgacha_grcwt8.webp"
)

NAME_BY_KEY = {c["key"]: c["name"] for c in CHARACTER_POOL}


def _anim(url, w=300):
    return url.replace("/upload/", f"/upload/f_webp,w_{w}/", 1)


def _star_str(rarity):
    return "★★★★★" if rarity in ("5L", "5S") else "★★★★"


def _build_gacha_embeds(results, is_new_list):
    embeds = []

    for r, is_new in zip(results, is_new_list):
        e = discord.Embed(
            color=RARITY_COLOR.get(r["rarity"], EMBED_COLOR)
        )

        e.set_thumbnail(
            url=_anim(r["url"], 90)
        )

        stars = _star_str(r["rarity"])
        val = f"{stars} ({RARITY_LABEL[r['rarity']]})"

        if is_new:
            val += "\n✨ **MỚI!**"

        e.add_field(
            name="\u200b",
            value="\u200b",
            inline=True,
        )

        e.add_field(
            name=r["name"],
            value=val,
            inline=True,
        )

        embeds.append(e)

    return embeds


def roll_one(state):
    state["pity5"] += 1
    state["pity4"] += 1

    # ===== XÁC ĐỊNH 5 SAO =====
    if state["pity5"] >= PITY_5_HARD:
        is_5 = True

    elif state["pity5"] >= PITY_5_SOFT:
        p = (
            RATE_5
            + (
                (state["pity5"] - PITY_5_SOFT)
                / (PITY_5_HARD - PITY_5_SOFT)
                * (SOFT_MAX_RATE - RATE_5)
            )
        )

        is_5 = random.random() < p

    else:
        is_5 = random.random() < RATE_5

    # ===== RA 5 SAO =====
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

    # ===== KHÔNG RA 5 SAO =====
    else:
        rarity = "4"
        state["pity4"] = 0

    pool = [
        c
        for c in CHARACTER_POOL
        if c["rarity"] == rarity
    ]

    return random.choice(pool)


async def handle_gacha(channel, author, bot, n):
    # ===== KIỂM TRA PVP =====
    if is_in_pvp(author.id):
        await channel.send(
            f"{author.mention} đang trong trận PvP, "
            f"xong trận mới quay gacha được nhé 🐟"
        )
        return

    # ===== TÍNH GIÁ =====
    cost = GACHA_COST if n == 1 else GACHA_COST5
    uid = author.id

    pts = await get_gems(uid)

    # ===== KHÔNG ĐỦ GEM =====
    if pts < cost:
        await channel.send(
            f"{author.mention} chưa đủ nguyên thạch quay "
            f"{n} lần (cần **{cost}❖**, em có **{pts}❖**). "
            f"Tích nguyên thạch mỗi tin nhắn nhé! 🐟"
        )
        return

    # ===== TRỪ GEM =====
    await spend_gems(uid, cost)

    # ===== LẤY TRẠNG THÁI PITY =====
    state = await get_state(uid)

    # ===== QUAY =====
    results = [
        roll_one(state)
        for _ in range(n)
    ]

    # ===== LƯU PITY =====
    await set_state(
        uid,
        state["pity5"],
        state["pity4"],
        state["guarantee5"],
    )

    # ===== KIỂM TRA THẺ MỚI =====
    owned = {
        c["char_key"]: c["dup_count"]
        for c in await get_collection(uid)
    }

    local_seen = {}
    is_new_list = []

    for r in results:
        base = owned.get(r["key"], 0)
        seen = local_seen.get(r["key"], 0)

        is_new_list.append(
            (base + seen) == 0
        )

        local_seen[r["key"]] = seen + 1

    # ===== HIỆU ỨNG ĐANG QUAY =====
    roll = discord.Embed(
        title="🎰 Đang quay...",
        color=EMBED_COLOR,
    )

    roll.set_image(
        url=GACHA_ROLL_GIF
    )

    msg = await channel.send(
        embed=roll
    )

    await asyncio.sleep(5.2)

    try:
        await msg.delete()
    except Exception:
        pass

    # ===== HIỂN THỊ KẾT QUẢ =====
    embeds = _build_gacha_embeds(
        results,
        is_new_list,
    )

    await channel.send(
        content=(
            f"🎴 Kết quả quay **{n} lần** "
            f"của {author.mention}:"
        ),
        embeds=embeds,
    )

    # ===== LƯU THẺ =====
    for r in results:
        await add_card(
            uid,
            r["key"],
            r["rarity"],
        )


async def handle_collection(channel, author, bot):
    uid = author.id

    rows = await get_collection(uid)

    owned = {
        r["char_key"]: (
            r["dup_count"],
            r["lvl"],
        )
        for r in rows
    }

    five = []
    four = []
    locked = []

    for c in CHARACTER_POOL:
        sao = (
            "5★"
            if c["rarity"].startswith("5")
            else "4★"
        )

        # ===== ĐÃ SỞ HỮU =====
        if c["key"] in owned:
            cnt, lvl = owned[c["key"]]

            emoji = (
                "🟡"
                if c["rarity"].startswith("5")
                else "🟣"
            )

            line = (
                f"{emoji} {c['name']} "
                f"({sao}) Lv{lvl} x{cnt}"
            )

            if c["rarity"].startswith("5"):
                five.append(line)
            else:
                four.append(line)

        # ===== CHƯA CÓ =====
        else:
            locked.append(
                f"🔒 {c['name']} ({sao}) x0"
            )

    blocks = []

    if five:
        blocks.append("\n".join(five))

    if four:
        blocks.append("\n".join(four))

    if locked:
        blocks.append("\n".join(locked))

    desc = (
        "\n\n".join(blocks)
        if blocks
        else "Chưa có thẻ nào."
    )

    total = sum(
        v[0]
        for v in owned.values()
    )

    e = discord.Embed(
        title=f"🎴 Kho thẻ của {author.display_name}",
        color=EMBED_COLOR,
    )

    e.description = desc

    e.set_footer(
        text=f"Đã có {len(owned)}/{len(CHARACTER_POOL)} • {total} thẻ"
    )

    await channel.send(embed=e)


# ============================================================
# GACHA VIEW - COMPONENTS V2
# ============================================================

class GachaView(discord.ui.LayoutView):
    def __init__(self, bot, author, gems):
        super().__init__(timeout=180)

        self.bot = bot
        self.author = author
        self.message = None

        # ====================================================
        # NÚT QUAY 1 LẦN
        # ====================================================

        self.btn_1 = discord.ui.Button(
            label="🎯 Quay 1 lần (50❖)",
            style=discord.ButtonStyle.primary,
        )

        self.btn_1.callback = lambda interaction: (
            self._run(interaction, 1)
        )

        # ====================================================
        # NÚT QUAY 5 LẦN
        # ====================================================

        self.btn_5 = discord.ui.Button(
            label="🎯 Quay 5 lần (250❖)",
            style=discord.ButtonStyle.success,
        )

        self.btn_5.callback = lambda interaction: (
            self._run(interaction, 5)
        )

        # ====================================================
        # ACTION ROW
        #
        # Chứa 2 nút
        # ====================================================

        self.button_row = discord.ui.ActionRow()

        self.button_row.add_item(self.btn_1)
        self.button_row.add_item(self.btn_5)

        # ====================================================
        # TEXT HIỂN THỊ TRONG CONTAINER
        # ====================================================

        self.gacha_text = discord.ui.TextDisplay(
            content=(
                "# 🎰 Gacha Thẻ Genshin\n"
                f"Nguyên thạch hiện có: **{gems}❖**\n"
                "Chọn số lượt quay:\n\n"
                "1 lần = 50❖ • 5 lần = 250❖"
            )
        )

        # ====================================================
        # CONTAINER
        #
        # Đây chính là khung bao gồm:
        #
        # TextDisplay
        #      ↓
        # ActionRow
        #   ├── Quay 1 lần
        #   └── Quay 5 lần
        # ====================================================

        self.container = discord.ui.Container(
            self.gacha_text,
            self.button_row,
            accent_color=EMBED_COLOR,
        )

        # Thêm Container vào LayoutView
        self.add_item(self.container)

    # ========================================================
    # HẾT THỜI GIAN
    # ========================================================

    async def on_timeout(self):
        # Tắt 2 nút
        for item in self.button_row.children:
            item.disabled = True

        try:
            if self.message:
                await self.message.edit(view=self)
        except Exception:
            pass

    # ========================================================
    # CHỈ CHỦ MESSAGE ĐƯỢC BẤM
    # ========================================================

    async def interaction_check(self, interaction):
        return interaction.user.id == self.author.id

    # ========================================================
    # XỬ LÝ BẤM NÚT
    #
    # LOGIC GIỮ NGUYÊN
    # ========================================================

    async def _run(self, interaction, n):

        # Kiểm tra PvP
        if is_in_pvp(interaction.user.id):
            await interaction.response.send_message(
                "Em đang trong trận PvP, "
                "xong trận mới quay gacha được nhé 🐟",
                ephemeral=True,
            )
            return

        # Tắt nút sau khi bấm
        for item in self.button_row.children:
            item.disabled = True

        # Cập nhật giao diện
        await interaction.response.edit_message(
            view=self
        )

        # Chạy logic gacha cũ
        await handle_gacha(
            interaction.channel,
            interaction.user,
            self.bot,
            n,
        )