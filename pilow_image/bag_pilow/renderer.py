from __future__ import annotations

import io
from pathlib import Path

import aiohttp
from PIL import Image, ImageDraw, ImageFont, ImageFilter


# ============================================================
# CONFIG
# ============================================================

WIDTH = 1200
HEIGHT = 700

BASE_DIR = Path(__file__).resolve().parent
FONT_DIR = BASE_DIR / "fonts"
BACKGROUND_PATH = BASE_DIR / "background.png"


# ============================================================
# FONT
# ============================================================

def get_font(size: int, bold: bool = False):
    """
    Font ưu tiên:
    pilow_image/bag_pilow/fonts/
    """

    if bold:
        names = [
            "NotoSans-Bold.ttf",
            "BeVietnamPro-Bold.ttf",
            "Inter-Bold.ttf",
            "DejaVuSans-Bold.ttf",
        ]
    else:
        names = [
            "NotoSans-Regular.ttf",
            "BeVietnamPro-Regular.ttf",
            "Inter-Regular.ttf",
            "DejaVuSans.ttf",
        ]

    for name in names:
        path = FONT_DIR / name

        if path.exists():
            return ImageFont.truetype(str(path), size)

    system_fonts = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]

    for path in system_fonts:
        if Path(path).exists():
            return ImageFont.truetype(path, size)

    return ImageFont.load_default()


# ============================================================
# HELPERS
# ============================================================

def rounded(draw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(
        box,
        radius=radius,
        fill=fill,
        outline=outline,
        width=width,
    )


def center_text(draw, box, text, font, fill):
    x1, y1, x2, y2 = box

    bbox = draw.textbbox((0, 0), text, font=font)

    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]

    x = x1 + (x2 - x1 - w) / 2
    y = y1 + (y2 - y1 - h) / 2 - bbox[1]

    draw.text(
        (x, y),
        text,
        font=font,
        fill=fill,
    )


def add_shadow(
    img,
    box,
    radius=25,
    shadow=(0, 0, 0, 120),
    blur=12,
    offset=(0, 8),
):
    layer = Image.new(
        "RGBA",
        img.size,
        (0, 0, 0, 0),
    )

    draw = ImageDraw.Draw(layer)

    x1, y1, x2, y2 = box

    draw.rounded_rectangle(
        (
            x1 + offset[0],
            y1 + offset[1],
            x2 + offset[0],
            y2 + offset[1],
        ),
        radius=radius,
        fill=shadow,
    )

    layer = layer.filter(
        ImageFilter.GaussianBlur(blur)
    )

    img.alpha_composite(layer)


# ============================================================
# BACKGROUND
# ============================================================

def create_background():
    if BACKGROUND_PATH.exists():
        try:
            bg = Image.open(
                BACKGROUND_PATH
            ).convert("RGBA")

            bg = bg.resize(
                (WIDTH, HEIGHT),
                Image.Resampling.LANCZOS,
            )

            # Tối background
            overlay = Image.new(
                "RGBA",
                (WIDTH, HEIGHT),
                (5, 7, 12, 105),
            )

            bg.alpha_composite(overlay)

            return bg

        except Exception:
            pass

    # Gradient background
    img = Image.new(
        "RGBA",
        (WIDTH, HEIGHT),
        (12, 15, 23, 255),
    )

    pixels = img.load()

    for y in range(HEIGHT):
        ratio = y / HEIGHT

        r = int(12 + ratio * 8)
        g = int(15 + ratio * 10)
        b = int(23 + ratio * 14)

        for x in range(WIDTH):
            pixels[x, y] = (
                r,
                g,
                b,
                255,
            )

    # Ánh sáng nhẹ
    glow = Image.new(
        "RGBA",
        (WIDTH, HEIGHT),
        (0, 0, 0, 0),
    )

    gd = ImageDraw.Draw(glow)

    gd.ellipse(
        (-150, -150, 550, 500),
        fill=(70, 200, 180, 35),
    )

    gd.ellipse(
        (800, 300, 1400, 900),
        fill=(70, 120, 220, 25),
    )

    glow = glow.filter(
        ImageFilter.GaussianBlur(100)
    )

    img.alpha_composite(glow)

    return img


# ============================================================
# AVATAR
# ============================================================

async def download_avatar(url):
    if not url:
        return None

    try:
        timeout = aiohttp.ClientTimeout(total=10)

        async with aiohttp.ClientSession(
            timeout=timeout
        ) as session:

            async with session.get(url) as response:

                if response.status != 200:
                    return None

                data = await response.read()

        avatar = Image.open(
            io.BytesIO(data)
        ).convert("RGBA")

        return avatar

    except Exception:
        return None


def draw_avatar(img, avatar, center, size):
    if avatar is None:
        # Placeholder
        draw = ImageDraw.Draw(img)

        x, y = center

        draw.ellipse(
            (
                x - size // 2,
                y - size // 2,
                x + size // 2,
                y + size // 2,
            ),
            fill=(38, 45, 57, 255),
            outline=(120, 220, 205, 255),
            width=5,
        )

        return

    avatar = avatar.resize(
        (size, size),
        Image.Resampling.LANCZOS,
    )

    mask = Image.new(
        "L",
        (size, size),
        0,
    )

    md = ImageDraw.Draw(mask)

    md.ellipse(
        (0, 0, size, size),
        fill=255,
    )

    x = center[0] - size // 2
    y = center[1] - size // 2

    # Glow
    glow = Image.new(
        "RGBA",
        (size + 70, size + 70),
        (0, 0, 0, 0),
    )

    gd = ImageDraw.Draw(glow)

    gd.ellipse(
        (10, 10, size + 60, size + 60),
        fill=(80, 220, 200, 80),
    )

    glow = glow.filter(
        ImageFilter.GaussianBlur(20)
    )

    img.alpha_composite(
        glow,
        (x - 35, y - 35),
    )

    # Outer ring
    draw = ImageDraw.Draw(img)

    draw.ellipse(
        (
            x - 10,
            y - 10,
            x + size + 10,
            y + size + 10,
        ),
        fill=(17, 21, 30, 255),
        outline=(91, 212, 195, 255),
        width=5,
    )

    img.paste(
        avatar,
        (x, y),
        mask,
    )

    # Inner border
    draw.ellipse(
        (
            x,
            y,
            x + size,
            y + size,
        ),
        outline=(215, 255, 248, 190),
        width=2,
    )


# ============================================================
# GEM ICON
# ============================================================

def draw_gem(draw, center, size=30):
    x, y = center

    points = [
        (x, y - size),
        (x + size, y),
        (x, y + size),
        (x - size, y),
    ]

    draw.polygon(
        points,
        fill=(93, 225, 211),
        outline=(225, 255, 251),
    )

    draw.polygon(
        [
            (x, y - size + 5),
            (x + size - 7, y),
            (x, y + 5),
        ],
        fill=(190, 255, 247),
    )

    draw.line(
        (
            x,
            y - size + 5,
            x,
            y + size - 5,
        ),
        fill=(45, 160, 153),
        width=2,
    )


# ============================================================
# MORA ICON
# ============================================================

def draw_mora(draw, center, size=30):
    x, y = center

    draw.ellipse(
        (
            x - size,
            y - size,
            x + size,
            y + size,
        ),
        fill=(221, 174, 64),
        outline=(255, 230, 150),
        width=3,
    )

    draw.ellipse(
        (
            x - size + 7,
            y - size + 7,
            x + size - 7,
            y + size - 7,
        ),
        outline=(177, 124, 32),
        width=2,
    )

    font = get_font(25, True)

    center_text(
        draw,
        (
            x - size,
            y - size,
            x + size,
            y + size,
        ),
        "M",
        font,
        (105, 67, 18),
    )


# ============================================================
# RESOURCE CARD
# ============================================================

def draw_resource_card(
    img,
    box,
    title,
    value,
    icon,
):
    draw = ImageDraw.Draw(img)

    x1, y1, x2, y2 = box

    add_shadow(
        img,
        box,
        radius=28,
        blur=14,
    )

    # Card
    rounded(
        draw,
        box,
        28,
        fill=(25, 31, 43, 245),
        outline=(78, 96, 111, 230),
        width=2,
    )

    # Top highlight
    draw.line(
        (
            x1 + 30,
            y1 + 2,
            x2 - 30,
            y1 + 2,
        ),
        fill=(100, 220, 204, 150),
        width=2,
    )

    # Icon circle
    icon_center = (
        x1 + 85,
        (y1 + y2) // 2,
    )

    draw.ellipse(
        (
            icon_center[0] - 50,
            icon_center[1] - 50,
            icon_center[0] + 50,
            icon_center[1] + 50,
        ),
        fill=(38, 46, 60, 255),
        outline=(79, 101, 115, 180),
        width=2,
    )

    if icon == "gem":
        draw_gem(
            draw,
            icon_center,
            28,
        )
    else:
        draw_mora(
            draw,
            icon_center,
            28,
        )

    # Title
    draw.text(
        (
            x1 + 155,
            y1 + 28,
        ),
        title,
        font=get_font(21, True),
        fill=(155, 170, 184),
    )

    # Value
    value_text = f"{value:,}"

    draw.text(
        (
            x1 + 155,
            y1 + 65,
        ),
        value_text,
        font=get_font(42, True),
        fill=(248, 250, 252),
    )


# ============================================================
# LEVEL
# ============================================================

def draw_level(
    img,
    x,
    y,
    level,
    current_xp,
    max_xp,
):
    draw = ImageDraw.Draw(img)

    # LEVEL label
    draw.text(
        (x, y),
        "LEVEL",
        font=get_font(18, True),
        fill=(132, 149, 164),
    )

    # Level number
    draw.text(
        (
            x,
            y + 23,
        ),
        str(level),
        font=get_font(54, True),
        fill=(245, 248, 250),
    )

    # XP text
    xp_text = (
        f"{current_xp:,} / "
        f"{max_xp:,} XP"
    )

    draw.text(
        (
            x + 105,
            y + 53,
        ),
        xp_text,
        font=get_font(18, False),
        fill=(135, 151, 165),
    )

    # XP bar
    bar_x = x + 105
    bar_y = y + 28
    bar_w = 400
    bar_h = 22

    rounded(
        draw,
        (
            bar_x,
            bar_y,
            bar_x + bar_w,
            bar_y + bar_h,
        ),
        11,
        fill=(10, 14, 21, 240),
        outline=(62, 76, 89, 220),
        width=2,
    )

    ratio = 0

    if max_xp > 0:
        ratio = max(
            0,
            min(
                current_xp / max_xp,
                1,
            ),
        )

    fill_w = int(
        (bar_w - 6) * ratio
    )

    if fill_w > 4:
        rounded(
            draw,
            (
                bar_x + 3,
                bar_y + 3,
                bar_x + 3 + fill_w,
                bar_y + bar_h - 3,
            ),
            8,
            fill=(71, 205, 184, 255),
        )


# ============================================================
# RANK
# ============================================================

def draw_rank(
    draw,
    x,
    y,
    rank,
):
    rank_colors = {
        1: (255, 215, 70),
        2: (215, 220, 230),
        3: (205, 145, 82),
    }

    color = rank_colors.get(
        rank,
        (105, 218, 199),
    )

    # Star
    draw.text(
        (x, y),
        "★",
        font=get_font(30, True),
        fill=color,
    )

    draw.text(
        (
            x + 38,
            y + 3,
        ),
        f"RANK {rank}",
        font=get_font(21, True),
        fill=color,
    )


# ============================================================
# MAIN
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
    Tạo giao diện Bag bằng Pillow.
    """

    img = create_background()
    draw = ImageDraw.Draw(img)

    # ========================================================
    # TITLE
    # ========================================================

    draw.text(
        (55, 35),
        "TÚI ĐỒ",
        font=get_font(43, True),
        fill=(248, 250, 252),
    )

    draw.text(
        (57, 87),
        "INVENTORY",
        font=get_font(17, True),
        fill=(91, 205, 190),
    )

    draw.line(
        (
            55,
            125,
            WIDTH - 55,
            125,
        ),
        fill=(72, 88, 101, 190),
        width=2,
    )

    # ========================================================
    # MAIN PROFILE
    # ========================================================

    profile_box = (
        55,
        155,
        1145,
        385,
    )

    add_shadow(
        img,
        profile_box,
        radius=32,
        blur=16,
    )

    rounded(
        draw,
        profile_box,
        32,
        fill=(21, 27, 39, 245),
        outline=(79, 98, 113, 230),
        width=2,
    )

    # ========================================================
    # AVATAR
    # ========================================================

    avatar_url = None

    try:
        avatar_url = str(
            target.display_avatar.url
        )
    except Exception:
        pass

    avatar = await download_avatar(
        avatar_url
    )

    draw_avatar(
        img,
        avatar,
        center=(170, 270),
        size=190,
    )

    # ========================================================
    # NAME
    # ========================================================

    name = str(
        getattr(
            target,
            "display_name",
            "Unknown",
        )
    )

    # Giới hạn tên dài
    if len(name) > 20:
        name = name[:19] + "…"

    draw.text(
        (300, 190),
        name,
        font=get_font(39, True),
        fill=(250, 252, 253),
    )

    # Rank
    draw_rank(
        draw,
        305,
        245,
        rank,
    )

    # Level
    current_xp = xp % points_per_level

    draw_level(
        img,
        300,
        295,
        level,
        current_xp,
        points_per_level,
    )

    # ========================================================
    # RESOURCE CARDS
    # ========================================================

    draw_resource_card(
        img,
        (
            55,
            420,
            575,
            570,
        ),
        "NGUYÊN THẠCH",
        gems,
        "gem",
    )

    draw_resource_card(
        img,
        (
            625,
            420,
            1145,
            570,
        ),
        "MORA",
        mora,
        "mora",
    )

    # ========================================================
    # FOOTER
    # ========================================================

    footer = (
        "Mỗi tin nhắn   +5 💠   •   "
        "+500 🪙   •   +10 XP"
    )

    center_text(
        draw,
        (
            55,
            610,
            1145,
            650,
        ),
        footer,
        get_font(17, False),
        (110, 126, 141),
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
