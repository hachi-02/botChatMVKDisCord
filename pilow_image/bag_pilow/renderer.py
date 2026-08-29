from __future__ import annotations

import io
import os
from pathlib import Path

import aiohttp
from PIL import Image, ImageDraw, ImageFont, ImageFilter


# ============================================================
# CONFIG
# ============================================================

WIDTH = 1100
HEIGHT = 620

BASE_DIR = Path(__file__).resolve().parent

# Có thể bỏ background.png vào cùng folder này.
BACKGROUND_PATH = BASE_DIR / "background.png"

# Font:
# Ưu tiên font custom đặt trong folder bag_pilow/fonts/
FONT_DIR = BASE_DIR / "fonts"

FONT_CANDIDATES = [
    FONT_DIR / "NotoSans-Regular.ttf",
    FONT_DIR / "NotoSans-Bold.ttf",
    FONT_DIR / "BeVietnamPro-Regular.ttf",
    FONT_DIR / "BeVietnamPro-Bold.ttf",
    FONT_DIR / "Inter-Regular.ttf",
    FONT_DIR / "Inter-Bold.ttf",
]

# Font hệ thống dự phòng
SYSTEM_FONTS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


# ============================================================
# FONT
# ============================================================

def _find_font(bold: bool = False):
    names = [
        "NotoSans-Bold.ttf" if bold else "NotoSans-Regular.ttf",
        "BeVietnamPro-Bold.ttf" if bold else "BeVietnamPro-Regular.ttf",
        "Inter-Bold.ttf" if bold else "Inter-Regular.ttf",
    ]

    for name in names:
        path = FONT_DIR / name
        if path.exists():
            return path

    # Thử font system
    if bold:
        system = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
        ]
    else:
        system = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        ]

    for path in system:
        if os.path.exists(path):
            return path

    return None


def _font(size: int, bold: bool = False):
    path = _find_font(bold)

    if path:
        return ImageFont.truetype(str(path), size)

    return ImageFont.load_default()


# ============================================================
# DRAW HELPERS
# ============================================================

def _rounded_rectangle(
    img: Image.Image,
    box,
    radius,
    fill,
    outline=None,
    width=1,
):
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle(
        box,
        radius=radius,
        fill=fill,
        outline=outline,
        width=width,
    )


def _center_text(draw, box, text, font, fill):
    x1, y1, x2, y2 = box

    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]

    x = x1 + ((x2 - x1) - tw) / 2
    y = y1 + ((y2 - y1) - th) / 2 - bbox[1]

    draw.text((x, y), text, font=font, fill=fill)


def _fit_text(draw, text, max_width, font_size, bold=False):
    size = font_size

    while size >= 12:
        font = _font(size, bold)
        bbox = draw.textbbox((0, 0), text, font=font)

        if bbox[2] - bbox[0] <= max_width:
            return font

        size -= 1

    return _font(12, bold)


def _hex_to_rgb(hex_color):
    hex_color = hex_color.replace("#", "")
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


# ============================================================
# BACKGROUND
# ============================================================

def _create_background():
    img = Image.new("RGBA", (WIDTH, HEIGHT), (18, 21, 30, 255))

    # Nếu có background.png thì dùng background đó
    if BACKGROUND_PATH.exists():
        try:
            bg = Image.open(BACKGROUND_PATH).convert("RGBA")
            bg = bg.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)

            # Làm tối background để chữ nổi hơn
            overlay = Image.new("RGBA", (WIDTH, HEIGHT), (5, 8, 15, 115))
            bg.alpha_composite(overlay)

            return bg
        except Exception:
            pass

    # Background gradient giả lập
    pixels = img.load()

    for y in range(HEIGHT):
        ratio = y / HEIGHT

        r = int(17 + ratio * 5)
        g = int(21 + ratio * 8)
        b = int(31 + ratio * 15)

        for x in range(WIDTH):
            pixels[x, y] = (r, g, b, 255)

    # Ánh sáng góc phải
    glow = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)

    gd.ellipse(
        (650, -170, 1250, 430),
        fill=(80, 210, 190, 45),
    )

    glow = glow.filter(ImageFilter.GaussianBlur(90))
    img.alpha_composite(glow)

    return img


# ============================================================
# AVATAR
# ============================================================

async def _download_avatar(url: str | None):
    if not url:
        return None

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:

                if response.status != 200:
                    return None

                data = await response.read()

        avatar = Image.open(io.BytesIO(data)).convert("RGBA")

        return avatar

    except Exception:
        return None


def _draw_avatar(img, avatar, center, size):
    if avatar is None:
        return

    avatar = avatar.resize(
        (size, size),
        Image.Resampling.LANCZOS,
    )

    mask = Image.new("L", (size, size), 0)
    md = ImageDraw.Draw(mask)

    md.ellipse(
        (0, 0, size, size),
        fill=255,
    )

    x = center[0] - size // 2
    y = center[1] - size // 2

    # Glow
    glow = Image.new("RGBA", (size + 24, size + 24), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)

    gd.ellipse(
        (8, 8, size + 16, size + 16),
        fill=(60, 220, 195, 90),
    )

    glow = glow.filter(ImageFilter.GaussianBlur(12))

    img.alpha_composite(
        glow,
        (x - 12, y - 12),
    )

    img.paste(
        avatar,
        (x, y),
        mask,
    )

    draw = ImageDraw.Draw(img)

    draw.ellipse(
        (x - 3, y - 3, x + size + 3, y + size + 3),
        outline=(100, 230, 210, 220),
        width=3,
    )


# ============================================================
# ICONS
# ============================================================

def _draw_gem(draw, center, radius=18):
    x, y = center

    points = [
        (x, y - radius),
        (x + radius, y),
        (x, y + radius),
        (x - radius, y),
    ]

    draw.polygon(
        points,
        fill=(110, 235, 220),
        outline=(210, 255, 250),
    )

    draw.polygon(
        [
            (x, y - radius + 5),
            (x + radius - 5, y),
            (x, y + 4),
        ],
        fill=(205, 255, 250),
    )


def _draw_coin(draw, center, radius=18):
    x, y = center

    draw.ellipse(
        (x - radius, y - radius, x + radius, y + radius),
        fill=(220, 174, 64),
        outline=(255, 225, 130),
        width=2,
    )

    font = _font(19, True)

    _center_text(
        draw,
        (
            x - radius,
            y - radius,
            x + radius,
            y + radius,
        ),
        "M",
        font,
        (90, 55, 10),
    )


# ============================================================
# RESOURCE CARD
# ============================================================

def _draw_resource_card(
    img,
    box,
    title,
    value,
    icon_type,
):
    draw = ImageDraw.Draw(img)

    x1, y1, x2, y2 = box

    # Shadow
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)

    sd.rounded_rectangle(
        (x1 + 4, y1 + 7, x2 + 4, y2 + 7),
        radius=22,
        fill=(0, 0, 0, 100),
    )

    shadow = shadow.filter(ImageFilter.GaussianBlur(8))
    img.alpha_composite(shadow)

    # Card
    _rounded_rectangle(
        img,
        box,
        22,
        fill=(29, 35, 47, 235),
        outline=(75, 93, 108, 170),
        width=2,
    )

    # Icon circle
    icon_x = x1 + 45
    icon_y = (y1 + y2) // 2

    draw.ellipse(
        (
            icon_x - 27,
            icon_y - 27,
            icon_x + 27,
            icon_y + 27,
        ),
        fill=(40, 49, 61, 255),
        outline=(90, 110, 120, 130),
        width=2,
    )

    if icon_type == "gem":
        _draw_gem(draw, (icon_x, icon_y), 16)
    else:
        _draw_coin(draw, (icon_x, icon_y), 16)

    # Text
    title_font = _font(18, False)
    value_font = _font(27, True)

    draw.text(
        (x1 + 82, y1 + 18),
        title,
        font=title_font,
        fill=(166, 178, 193),
    )

    draw.text(
        (x1 + 82, y1 + 45),
        f"{value:,}",
        font=value_font,
        fill=(245, 248, 250),
    )


# ============================================================
# XP BAR
# ============================================================

def _draw_xp_bar(
    img,
    x,
    y,
    width,
    progress,
    total,
):
    draw = ImageDraw.Draw(img)

    ratio = 0 if total <= 0 else max(0, min(progress / total, 1))

    # Label
    label_font = _font(18, True)

    draw.text(
        (x, y - 35),
        "TIẾN ĐỘ CẤP",
        font=label_font,
        fill=(205, 214, 220),
    )

    # Background
    bar_y = y

    draw.rounded_rectangle(
        (x, bar_y, x + width, bar_y + 22),
        radius=11,
        fill=(11, 15, 22, 230),
        outline=(66, 80, 92, 200),
        width=2,
    )

    fill_width = int(width * ratio)

    if fill_width > 4:
        draw.rounded_rectangle(
            (
                x + 3,
                bar_y + 3,
                x + fill_width,
                bar_y + 19,
            ),
            radius=8,
            fill=(67, 205, 184, 255),
        )

    # XP text
    xp_font = _font(16, False)

    xp_text = f"{progress:,} / {total:,} XP"

    bbox = draw.textbbox(
        (0, 0),
        xp_text,
        font=xp_font,
    )

    draw.text(
        (
            x + width - (bbox[2] - bbox[0]),
            bar_y + 31,
        ),
        xp_text,
        font=xp_font,
        fill=(145, 158, 171),
    )


# ============================================================
# MAIN RENDER
# ============================================================

async def create_bag(
    target,
    gems: int,
    mora: int,
    rank: int,
    level: int,
    xp: int,
    points_per_level: int = 100,
):
    """
    Render giao diện Bag bằng Pillow.

    target:
        Discord Member/User object.

    gems:
        Số Nguyên Thạch.

    mora:
        Số Mora.

    rank:
        Rank hiện tại.

    level:
        Level hiện tại.

    xp:
        XP hiện tại.

    points_per_level:
        XP cần để lên cấp.
    """

    img = _create_background()
    draw = ImageDraw.Draw(img)

    # ========================================================
    # HEADER
    # ========================================================

    # Logo / avatar bot
    draw.text(
        (50, 38),
        "BAG",
        font=_font(38, True),
        fill=(245, 248, 250),
    )

    draw.text(
        (50, 82),
        "TÀI SẢN NHÂN VẬT",
        font=_font(15, False),
        fill=(115, 202, 190),
    )

    # đường line
    draw.line(
        (50, 120, WIDTH - 50, 120),
        fill=(65, 82, 95, 180),
        width=1,
    )

    # ========================================================
    # PROFILE CARD
    # ========================================================

    profile_box = (50, 150, 1050, 310)

    _rounded_rectangle(
        img,
        profile_box,
        28,
        fill=(24, 30, 42, 235),
        outline=(72, 91, 105, 180),
        width=2,
    )

    # Avatar
    avatar_url = None

    try:
        avatar_url = target.display_avatar.url
    except Exception:
        pass

    avatar = await _download_avatar(
        str(avatar_url) if avatar_url else None
    )

    _draw_avatar(
        img,
        avatar,
        (140, 230),
        110,
    )

    # Username
    username = getattr(
        target,
        "display_name",
        "Unknown",
    )

    username = str(username)

    username_font = _fit_text(
        draw,
        username,
        480,
        32,
        True,
    )

    draw.text(
        (225, 178),
        username,
        font=username_font,
        fill=(248, 250, 252),
    )

    # Rank
    rank_colors = {
        1: (255, 215, 0),
        2: (205, 215, 225),
        3: (205, 145, 80),
    }

    rank_color = rank_colors.get(
        rank,
        (90, 210, 195),
    )

    rank_text = f"RANK #{rank}"

    draw.text(
        (227, 224),
        rank_text,
        font=_font(19, True),
        fill=rank_color,
    )

    # Level badge
    badge = (820, 180, 1005, 260)

    _rounded_rectangle(
        img,
        badge,
        20,
        fill=(35, 43, 56, 255),
        outline=(91, 113, 125, 190),
        width=2,
    )

    draw.text(
        (845, 192),
        "LEVEL",
        font=_font(15, True),
        fill=(135, 153, 165),
    )

    draw.text(
        (845, 213),
        str(level),
        font=_font(34, True),
        fill=(245, 248, 250),
    )

    # ========================================================
    # RESOURCE CARDS
    # ========================================================

    _draw_resource_card(
        img,
        (50, 340, 525, 445),
        "NGUYÊN THẠCH",
        gems,
        "gem",
    )

    _draw_resource_card(
        img,
        (575, 340, 1050, 445),
        "MORA",
        mora,
        "coin",
    )

    # ========================================================
    # XP
    # ========================================================

    current_xp = xp % points_per_level

    _draw_xp_bar(
        img,
        50,
        500,
        1000,
        current_xp,
        points_per_level,
    )

    # ========================================================
    # FOOTER
    # ========================================================

    footer = "Mỗi tin nhắn  +5 💠   +500 Mora   +10 XP"

    _center_text(
        draw,
        (50, 565, 1050, 600),
        footer,
        _font(15, False),
        (110, 125, 140),
    )

    # ========================================================
    # OUTPUT
    # ========================================================

    output = io.BytesIO()

    img.convert("RGB").save(
        output,
        format="PNG",
        optimize=True,
    )

    output.seek(0)

    return output
