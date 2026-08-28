import asyncio
import io

import aiohttp
from PIL import Image, ImageDraw, ImageFont

from config import PVP_ENERGY_MAX, PVP_SP_MAX
from .cards import ROLE_LABEL, ROLE_COLOR

FONT_PATH = "assets/fonts/DejaVuSans.ttf"

W, H = 1400, 900
BG = (24, 26, 35)
CARD_BG = (43, 47, 63)
BLUE = (88, 101, 242)
RED = (237, 66, 69)
WHITE = (240, 242, 246)
MUTED = (170, 175, 188)
GOLD = (241, 196, 15)
GREEN = (46, 204, 113)

PORTRAIT = 208
BAR_W = 118
HP_BAR_H = 14
EN_BAR_H = 10

_fonts = {}
_portrait_cache = {}


def _font(size: int):
    f = _fonts.get(size)
    if f is None:
        try:
            f = ImageFont.truetype(FONT_PATH, size)
        except Exception:
            f = ImageFont.load_default(size)
        _fonts[size] = f
    return f


def _text(draw, xy, s, size, fill, anchor="la"):
    draw.text(xy, s, font=_font(size), fill=fill, anchor=anchor)


def _lerp(c1, c2, t):
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))


def _bar(draw, x, y, w, h, pct, color, bg=(20, 22, 30)):
    draw.rounded_rectangle((x, y, x + w, y + h), radius=h // 2, fill=bg)
    if pct > 0:
        draw.rounded_rectangle((x, y, x + w * min(pct, 1.0), y + h), radius=h // 2, fill=color)


def _normalize(im: Image.Image) -> Image.Image:
    im = im.convert("RGBA")
    w, h = im.size
    s = min(w, h)
    l = (w - s) // 2
    t = (h - s) // 2
    return im.crop((l, t, l + s, t + s))


def _portrait(url: str, dead: bool) -> Image.Image:
    raw = _portrait_cache.get(url)
    if raw is None:
        base = Image.new("RGBA", (PORTRAIT, PORTRAIT), (60, 64, 82, 255))
        _text(ImageDraw.Draw(base), (PORTRAIT // 2, PORTRAIT // 2), "?", 60, MUTED, anchor="mm")
        return base
    im = _normalize(raw).resize((PORTRAIT, PORTRAIT))
    if dead:
        im = im.convert("L").convert("RGBA")
    return im


def _draw_card(img, draw, row_y, fighter, team_color, side):
    # side == "L": portrait trái, thông tin phải
    # side == "R": thông tin trái (right-aligned), portrait phải
    if side == "L":
        rect = (36, row_y, 566, row_y + 236)
        px, py = 52, row_y + 4
        info_x = 272
    else:
        rect = (834, row_y, 1364, row_y + 236)
        px, py = 1148, row_y + 4
        info_x = 1132

    border = (255, 210, 80) if fighter.stunned and fighter.alive else team_color
    draw.rounded_rectangle(rect, radius=18, fill=CARD_BG, outline=border, width=3)

    dead = not fighter.alive
    portrait = _portrait(fighter.url, dead)
    draw.rectangle((px - 4, py - 4, px + PORTRAIT + 4, py + PORTRAIT + 4), fill=(20, 22, 30))
    img.paste(portrait, (px, py), portrait)
    if dead:
        c = (px + PORTRAIT // 2, py + PORTRAIT // 2)
        draw.line((c[0] - 40, c[1] - 40, c[0] + 40, c[1] + 40), fill=RED, width=12)
        draw.line((c[0] - 40, c[1] + 40, c[0] + 40, c[1] - 40), fill=RED, width=12)

    eff_atk = round(fighter.atk * (1 + fighter.atk_buff))
    pct = max(0.0, fighter.hp / fighter.max_hp)
    hp_color = _lerp(RED, GREEN, pct)
    role_color = ROLE_COLOR.get(fighter.role, 0x95A5A6)

    if side == "L":
        _text(draw, (info_x, row_y + 4), fighter.name, 30, WHITE)
        _text(draw, (info_x, row_y + 40), ROLE_LABEL.get(fighter.role, fighter.role), 19,
              _hex(role_color))
        _bar(draw, info_x, row_y + 72, BAR_W, HP_BAR_H, pct, hp_color)
        _text(draw, (info_x + BAR_W + 10, row_y + 79), f"HP {max(0, fighter.hp)}/{fighter.max_hp}", 22, WHITE, anchor="lm")
        _text(draw, (info_x, row_y + 104), f"ATK {eff_atk}", 22, WHITE)
        _text(draw, (info_x, row_y + 132), f"SPD {fighter.spd}", 22, WHITE)
        _bar(draw, info_x, row_y + 158, BAR_W, EN_BAR_H, fighter.energy / PVP_ENERGY_MAX, GOLD)
        _text(draw, (info_x + BAR_W + 10, row_y + 163), f"EN {min(PVP_ENERGY_MAX, fighter.energy)}/{PVP_ENERGY_MAX}", 22, WHITE, anchor="lm")
        if not dead:
            extra = []
            if fighter.shield > 0:
                extra.append(f"SH {int(fighter.shield * 100)}%")
            if fighter.pending:
                extra.append("↻ 1 HĐ")
            if fighter.stunned:
                extra.append("STUN")
            if extra:
                _text(draw, (info_x, row_y + 192), "  ".join(extra), 20, GOLD)
    else:
        _text(draw, (info_x, row_y + 4), fighter.name, 30, WHITE, anchor="ra")
        _text(draw, (info_x, row_y + 40), ROLE_LABEL.get(fighter.role, fighter.role), 19,
              _hex(role_color), anchor="ra")
        _bar(draw, info_x - BAR_W, row_y + 72, BAR_W, HP_BAR_H, pct, hp_color)
        _text(draw, (info_x - BAR_W - 10, row_y + 79), f"HP {max(0, fighter.hp)}/{fighter.max_hp}", 22, WHITE, anchor="rm")
        _text(draw, (info_x, row_y + 104), f"ATK {eff_atk}", 22, WHITE, anchor="ra")
        _text(draw, (info_x, row_y + 132), f"SPD {fighter.spd}", 22, WHITE, anchor="ra")
        _bar(draw, info_x - BAR_W, row_y + 158, BAR_W, EN_BAR_H, fighter.energy / PVP_ENERGY_MAX, GOLD)
        _text(draw, (info_x - BAR_W - 10, row_y + 163), f"EN {min(PVP_ENERGY_MAX, fighter.energy)}/{PVP_ENERGY_MAX}", 22, WHITE, anchor="rm")
        if not dead:
            extra = []
            if fighter.shield > 0:
                extra.append(f"SH {int(fighter.shield * 100)}%")
            if fighter.pending:
                extra.append("↻ 1 HĐ")
            if fighter.stunned:
                extra.append("STUN")
            if extra:
                _text(draw, (info_x, row_y + 192), "  ".join(extra), 20, GOLD, anchor="ra")


def _hex(color: int) -> tuple:
    return (color >> 16) & 0xFF, (color >> 8) & 0xFF, color & 0xFF


def render_battle_image(battle) -> io.BytesIO:
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    draw.rounded_rectangle((60, 30, 86, 58), radius=14, fill=BLUE)
    _text(draw, (100, 30), battle.a_user.display_name.upper(), 30, WHITE)
    _text(draw, (100, 68), f"SP {battle.sp_a}/{PVP_SP_MAX}", 22, MUTED)

    draw.rounded_rectangle((1314, 30, 1340, 58), radius=14, fill=RED)
    _text(draw, (1300, 30), battle.b_user.display_name.upper(), 30, WHITE, anchor="ra")
    _text(draw, (1300, 68), f"SP {battle.sp_b}/{PVP_SP_MAX}", 22, MUTED, anchor="ra")

    cx, cy = 700, 56
    draw.ellipse((cx - 32, cy - 32, cx + 32, cy + 32), fill=(88, 101, 242))
    _text(draw, (cx, cy), "VS", 30, WHITE, anchor="mm")

    y = 124
    for i in range(3):
        _draw_card(img, draw, y, battle.team_a[i], BLUE, "L")
        _draw_card(img, draw, y, battle.team_b[i], RED, "R")
        y += 246

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


async def _load_one(session: aiohttp.ClientSession, url: str):
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                return
            data = await resp.read()
            im = Image.open(io.BytesIO(data))
            im.load()
            im = im.convert("RGBA")
            if getattr(im, "n_frames", 1) > 1:
                im.seek(0)
            _portrait_cache[url] = im
    except Exception:
        pass


async def prepare_battle_image(battle):
    urls = [f.url for f in battle.team_a + battle.team_b]
    missing = [u for u in urls if u not in _portrait_cache]
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
            await asyncio.gather(*(_load_one(session, u) for u in missing))
    except Exception:
        pass
    battle._img_ok = all(u in _portrait_cache for u in urls)