import asyncio
import io
import math
import os
import random

import aiohttp
import discord
from PIL import Image, ImageDraw, ImageFont, ImageSequence

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


def _thumb(url, w=400):
    return url.replace("/upload/", f"/upload/w_{w}/", 1)


def _anim(url, w=230):
    return url.replace("/upload/", f"/upload/f_gif,w_{w}/", 1)


async def _fetch_image(session, url):
    async with session.get(url) as resp:
        resp.raise_for_status()
        return await resp.read()


def _font_path():
    here = os.path.dirname(__file__)
    candidates = [
        os.path.join(here, "fonts", "NotoSans-Regular.ttf"),
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None


IMG_CACHE = {}
IMG_CACHE_MAX = 64


def _rarity_color(rarity):
    return (255, 215, 0) if rarity in ("5L", "5S") else (155, 89, 182)


def _star_points(cx, cy, r, n=5):
    pts = []
    for i in range(n * 2):
        ang = -math.pi / 2 + i * math.pi / n
        rad = r if i % 2 == 0 else r * 0.45
        pts.append((cx + rad * math.cos(ang), cy + rad * math.sin(ang)))
    return pts


def _draw_stars_row(draw, cx, cy, count, r, color):
    if count <= 0:
        return
    spacing = r * 2.4
    total = spacing * (count - 1)
    x = cx - total / 2
    for k in range(count):
        draw.polygon(_star_points(x + k * spacing, cy, r), fill=color)


def _vgradient(w, h, top, bottom):
    base = Image.new("RGB", (w, h), top)
    d = ImageDraw.Draw(base)
    for y in range(h):
        t = y / max(1, h - 1)
        col = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        d.line([(0, y), (w, y)], fill=col)
    return base


MAX_FRAMES = 16
GIF_FRAME_MS = 80


async def _get_img(session, r, w):
    key = r["key"]
    if key in IMG_CACHE:
        return key, IMG_CACHE[key]
    data = await _fetch_image(session, _anim(r["url"], w))
    if len(IMG_CACHE) < IMG_CACHE_MAX:
        IMG_CACHE[key] = data
    return key, data


async def _build_montage(results, is_new_list):
    font_path = _font_path()
    name_font = ImageFont.truetype(font_path, 26) if font_path else ImageFont.load_default()
    tag_font = ImageFont.truetype(font_path, 20) if font_path else ImageFont.load_default()

    cell_w = 230
    img_h = 320
    gap = 14
    pad = 16
    radius = 16
    n = len(results)
    total_w = pad * 2 + n * cell_w + (n - 1) * gap
    total_h = pad * 2 + img_h + 86

    async with aiohttp.ClientSession() as s:
        fetched = await asyncio.gather(*[_get_img(s, r, cell_w) for r in results])
    img_data = {k: d for k, d in fetched}

    cell_frames = []
    for r in results:
        data = img_data[r["key"]]
        try:
            im = Image.open(io.BytesIO(data))
        except Exception as e:
            print(f"LỖI OPEN IMG: {type(e).__name__}: {e}", flush=True)
            im = Image.new("RGBA", (cell_w, img_h), (60, 63, 68, 255))
        frames = []
        try:
            for fr in ImageSequence.Iterator(im):
                f = fr.convert("RGBA").copy()
                f.thumbnail((cell_w, img_h), Image.Resampling.LANCZOS)
                frames.append(f)
        except Exception:
            f = im.convert("RGBA").copy()
            f.thumbnail((cell_w, img_h), Image.Resampling.LANCZOS)
            frames = [f]
        if not frames:
            frames = [Image.new("RGBA", (cell_w, img_h), (60, 63, 68, 255))]
        if len(frames) > MAX_FRAMES:
            step = len(frames) / MAX_FRAMES
            frames = [frames[int(i * step)] for i in range(MAX_FRAMES)]
        cell_frames.append(frames)

    max_frames = max(len(f) for f in cell_frames)

    out_frames = []
    for t in range(max_frames):
        canvas = _vgradient(total_w, total_h, (28, 30, 35), (43, 45, 49))
        draw = ImageDraw.Draw(canvas)
        for i, (r, is_new) in enumerate(zip(results, is_new_list)):
            x0 = pad + i * (cell_w + gap)
            y0 = pad
            rarity_color = _rarity_color(r["rarity"])
            draw.rounded_rectangle(
                [x0, y0, x0 + cell_w, y0 + img_h],
                radius=radius,
                fill=(47, 49, 54),
                outline=rarity_color,
                width=3,
            )
            fr = cell_frames[i][t % len(cell_frames[i])]
            ix = x0 + (cell_w - fr.width) // 2
            iy = y0 + (img_h - fr.height) // 2
            canvas.paste(fr, (ix, iy), fr)

            name_y = y0 + img_h + 14
            draw.text((x0 + cell_w // 2, name_y), r["name"], font=name_font, fill=rarity_color, anchor="mm")
            star_y = name_y + 32
            n_stars = 5 if r["rarity"] in ("5L", "5S") else 4
            _draw_stars_row(draw, x0 + cell_w // 2, star_y, n_stars, 11, (255, 215, 0))
            if is_new:
                draw.text((x0 + cell_w // 2, star_y + 26), "MỚI!", font=tag_font, fill=(46, 204, 113), anchor="mm")
        out_frames.append(canvas)

    buf = io.BytesIO()
    out_frames[0].save(
        buf,
        format="GIF",
        save_all=True,
        append_images=out_frames[1:],
        duration=GIF_FRAME_MS,
        loop=0,
        disposal=2,
    )
    buf.seek(0)
    return discord.File(buf, filename="gacha_result.gif")


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

    task = asyncio.create_task(_build_montage(results, is_new_list))
    await asyncio.sleep(2.0)
    try:
        await msg.delete()
    except Exception:
        pass

    try:
        file = await task
        await channel.send(content=f"🎴 Kết quả quay **{n} lần** của {author.mention}:", file=file)
    except Exception as e:
        print(f"LỖI MONTAGE: {type(e).__name__}: {e}", flush=True)
        names = " | ".join(r["name"] for r in results)
        await channel.send(content=f"🎴 Kết quả quay **{n} lần** của {author.mention}: {names}")
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
