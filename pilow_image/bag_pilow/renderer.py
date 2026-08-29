
from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


# ============================================================
# CONFIG
# ============================================================

WIDTH = 900
HEIGHT = 390

BASE_DIR = Path(__file__).resolve().parent


# ============================================================
# COLORS
# ============================================================

TRANSPARENT = (0, 0, 0, 0)

# Card
CARD = (42, 42, 42, 245)
CARD_BORDER = None

# Text
WHITE = (235, 235, 235, 255)
GRAY = (165, 165, 165, 255)
DARK_GRAY = (90, 90, 90, 255)

# XP
XP_BACKGROUND = (55, 55, 55, 255)
XP_FILL = (75, 190, 110, 255)

# Resources
GEM = (145, 145, 145, 255)
MORA = (145, 145, 145, 255)


# ============================================================
# FONT
# ============================================================

def get_font(size: int, bold: bool = False):
    """
    Font chính trên Windows:
        Segoe UI
        Segoe UI Semibold / Bold
        Arial fallback

    Không dùng font custom nên tránh lỗi:
        OSError: unknown file format
    """

    windows_fonts = Path(
        r"C:\Windows\Fonts"
    )

    if bold:
        candidates = [
            windows_fonts / "segoeuib.ttf",   # Segoe UI Bold
            windows_fonts / "segoeuisb.ttf",  # Segoe UI Semibold
            windows_fonts / "arialbd.ttf",    # Arial Bold
        ]
    else:
        candidates = [
            windows_fonts / "segoeui.ttf",    # Segoe UI
            windows_fonts / "arial.ttf",      # Arial
        ]

    for path in candidates:
        if path.is_file():
            try:
                return ImageFont.truetype(
                    str(path),
                    size,
                )
            except (OSError, IOError):
                continue

    # ========================================================
    # Linux / Render
    # ========================================================

    if bold:
        linux_candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
        ]
    else:
        linux_candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        ]

    for path in linux_candidates:
        if Path(path).is_file():
            try:
                return ImageFont.truetype(
                    path,
                    size,
                )
            except (OSError, IOError):
                continue

    raise RuntimeError(
        "Không tìm thấy font hợp lệ."
    )


# ============================================================
# HELPERS
# ============================================================

def rounded(
    draw,
    box,
    radius,
    fill,
    outline=None,
    width=1,
):
    draw.rounded_rectangle(
        box,
        radius=radius,
        fill=fill,
        outline=outline,
        width=width,
    )


def text_size(
    draw,
    text,
    font,
):
    bbox = draw.textbbox(
        (0, 0),
        text,
        font=font,
    )

    return (
        bbox[2] - bbox[0],
        bbox[3] - bbox[1],
    )


def draw_center_vertical(
    draw,
    x,
    center_y,
    text,
    font,
    fill,
):
    """
    Vẽ text sao cho tâm chữ nằm đúng center_y.
    """

    bbox = draw.textbbox(
        (0, 0),
        text,
        font=font,
    )

    text_height = bbox[3] - bbox[1]

    y = center_y - text_height / 2 - bbox[1]

    draw.text(
        (x, y),
        text,
        font=font,
        fill=fill,
    )


def draw_center(
    draw,
    box,
    text,
    font,
    fill,
):
    """
    Căn giữa chính xác cả ngang lẫn dọc.
    """

    x1, y1, x2, y2 = box

    bbox = draw.textbbox(
        (0, 0),
        text,
        font=font,
    )

    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    x = (
        x1
        + (x2 - x1 - text_width) / 2
        - bbox[0]
    )

    y = (
        y1
        + (y2 - y1 - text_height) / 2
        - bbox[1]
    )

    draw.text(
        (x, y),
        text,
        font=font,
        fill=fill,
    )


def draw_right_center(
    draw,
    x_right,
    center_y,
    text,
    font,
    fill,
):
    """
    Căn phải + căn giữa theo chiều dọc.
    """

    bbox = draw.textbbox(
        (0, 0),
        text,
        font=font,
    )

    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    x = (
        x_right
        - text_width
        - bbox[0]
    )

    y = (
        center_y
        - text_height / 2
        - bbox[1]
    )

    draw.text(
        (x, y),
        text,
        font=font,
        fill=fill,
    )


# ============================================================
# XP CARD
# ============================================================

def draw_xp_card(
    draw,
    y,
    level,
    current_xp,
    max_xp,
):
    x1 = 20
    x2 = WIDTH - 20
    height = 100

    rounded(
        draw,
        (
            x1,
            y,
            x2,
            y + height,
        ),
        14,
        fill=CARD,
        outline=None,
        width=0,
    )

    # ========================================================
    # LEVEL
    # ========================================================

    level_text = f"LEVEL {level}"

    level_font = get_font(
        28,
        True,
    )

    draw_center_vertical(
        draw,
        x1 + 25,
        y + 30,
        level_text,
        level_font,
        WHITE,
    )

    # ========================================================
    # XP TEXT
    # ========================================================

    xp_text = (
        f"{current_xp:,} / "
        f"{max_xp:,} XP"
    )

    xp_font = get_font(
        23,
        True,
    )

    draw_right_center(
        draw,
        x2 - 25,
        y + 30,
        xp_text,
        xp_font,
        WHITE,
    )

    # ========================================================
    # XP BAR
    # ========================================================

    bar_x = x1 + 25
    bar_y = y + 55

    bar_width = (
        x2 - x1 - 50
    )

    bar_height = 22

    rounded(
        draw,
        (
            bar_x,
            bar_y,
            bar_x + bar_width,
            bar_y + bar_height,
        ),
        11,
        fill=XP_BACKGROUND,
    )

    if max_xp > 0:
        ratio = max(
            0,
            min(
                current_xp / max_xp,
                1,
            ),
        )
    else:
        ratio = 0

    fill_width = int(
        bar_width * ratio
    )

    if fill_width > 0:
        rounded(
            draw,
            (
                bar_x,
                bar_y,
                bar_x + fill_width,
                bar_y + bar_height,
            ),
            11,
            fill=XP_FILL,
        )


# ============================================================
# GEM ICON
# ============================================================

def draw_gem(
    draw,
    center_x,
    center_y,
    size=20,
):
    points = [
        (
            center_x,
            center_y - size,
        ),
        (
            center_x + size,
            center_y,
        ),
        (
            center_x,
            center_y + size,
        ),
        (
            center_x - size,
            center_y,
        ),
    ]

    draw.polygon(
        points,
        fill=GEM,
    )

    draw.line(
        (
            center_x,
            center_y - size + 3,
            center_x,
            center_y + size - 3,
        ),
        fill=(220, 245, 250, 255),
        width=2,
    )


# ============================================================
# MORA ICON
# ============================================================

def draw_mora(
    draw,
    center_x,
    center_y,
    size=20,
):
    draw.ellipse(
        (
            center_x - size,
            center_y - size,
            center_x + size,
            center_y + size,
        ),
        fill=MORA,
        outline=(240, 215, 145, 255),
        width=2,
    )

    draw_center(
        draw,
        (
            center_x - size,
            center_y - size,
            center_x + size,
            center_y + size,
        ),
        "M",
        get_font(
            15,
            True,
        ),
        (80, 55, 15, 255),
    )


# ============================================================
# RESOURCE CARD
# ============================================================

def draw_resource_card(
    draw,
    y,
    title,
    value,
    icon_type,
):
    x1 = 20
    x2 = WIDTH - 20
    height = 100

    rounded(
        draw,
        (
            x1,
            y,
            x2,
            y + height,
        ),
        14,
        fill=CARD,
        outline=None,
        width=0,
    )

    center_y = (
        y + height // 2
    )

    # ========================================================
    # ICON BACKGROUND
    # ========================================================

    draw.ellipse(
        (
            x1 + 20,
            center_y - 30,
            x1 + 80,
            center_y + 30,
        ),
        fill=(43, 43, 43, 255),
    )

    if icon_type == "gem":
        draw_gem(
            draw,
            x1 + 50,
            center_y,
            18,
        )
    else:
        draw_mora(
            draw,
            x1 + 50,
            center_y,
            18,
        )

    # ========================================================
    # TITLE
    # ========================================================

    title_font = get_font(
        27,
        True,
    )

    draw_center_vertical(
        draw,
        x1 + 105,
        center_y,
        title,
        title_font,
        WHITE,
    )

    # ========================================================
    # VALUE
    # ========================================================

    value_text = f"{value:,}"

    value_font = get_font(
        34,
        True,
    )

    draw_right_center(
        draw,
        x2 - 25,
        center_y,
        value_text,
        value_font,
        WHITE,
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
    Pillow chỉ render:

    1. XP
    2. Nguyên thạch
    3. Mora

    Background hoàn toàn transparent.
    """

    img = Image.new(
        "RGBA",
        (
            WIDTH,
            HEIGHT,
        ),
        TRANSPARENT,
    )

    draw = ImageDraw.Draw(img)

    # ========================================================
    # XP
    # ========================================================

    current_xp = (
        xp % points_per_level
    )

    draw_xp_card(
        draw,
        y=10,
        level=level,
        current_xp=current_xp,
        max_xp=points_per_level,
    )

    # ========================================================
    # GEMS
    # ========================================================

    draw_resource_card(
        draw,
        y=125,
        title="NGUYÊN THẠCH",
        value=gems,
        icon_type="gem",
    )

    # ========================================================
    # MORA
    # ========================================================

    draw_resource_card(
        draw,
        y=240,
        title="MORA",
        value=mora,
        icon_type="mora",
    )

    # ========================================================
    # OUTPUT
    # ========================================================

    output = io.BytesIO()

    img.save(
        output,
        format="PNG",
        optimize=True,
    )

    output.seek(0)

    return output
