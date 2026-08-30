
from __future__ import annotations

import io

from PIL import Image, ImageDraw

from pilow_image.bag_pilow.renderer import (
    WIDTH,
    CARD,
    WHITE,
    TRANSPARENT,
    get_font,
    rounded,
    draw_right_center,
    draw_center,
)


# ============================================================
# CANVAS
# ============================================================

CARD_GAP = 115
CARD_HEIGHT = 100

HEIGHT = 470


# ============================================================
# COLORS
# ============================================================

# ELO (vàng)
ELO_COLOR = (241, 196, 15, 255)
ELO_DARK = (96, 76, 12, 255)

# RANK (tím PvP)
RANK_COLOR = (155, 89, 182, 255)
RANK_DARK = (63, 34, 76, 255)

# WIN (xanh)
WIN_COLOR = (46, 204, 113, 255)
WIN_DARK = (20, 84, 48, 255)

# LOSS (đỏ)
LOSS_COLOR = (231, 76, 60, 255)
LOSS_DARK = (94, 30, 24, 255)


# ============================================================
# STAT CARD
# ============================================================

def draw_stat_card(
    draw,
    y,
    title,
    value,
    accent,
):
    x1 = 20
    x2 = WIDTH - 20

    height = 100

    # ========================================================
    # CARD
    # ========================================================

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

    center_y = y + height // 2

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
        fill=(
            43,
            43,
            43,
            255,
        ),
    )

    # ========================================================
    # ICON
    # ========================================================

    label, bg, label_color = accent

    draw_center(
        draw,
        (
            x1 + 20,
            center_y - 30,
            x1 + 80,
            center_y + 30,
        ),
        label,
        get_font(
            34,
            True,
        ),
        label_color,
    )

    # ========================================================
    # TITLE
    #
    # Dùng anchor="lm" để chữ căn giữa chiều dọc chính xác.
    # Đặc biệt xử lý tốt chữ tiếng Việt có dấu như:
    # HẠNG / THẮNG
    # ========================================================

    title_font = get_font(
        27,
        True,
    )

    draw.text(
        (
            x1 + 105,
            center_y,
        ),
        title,
        font=title_font,
        fill=WHITE,
        anchor="lm",
    )

    # ========================================================
    # VALUE
    # ========================================================

    value_font = get_font(
        34,
        True,
    )

    draw_right_center(
        draw,
        x2 - 25,
        center_y,
        value,
        value_font,
        WHITE,
    )


# ============================================================
# MAIN
# ============================================================

async def create_pvp_card(
    target,
    rating: int,
    wins: int,
    losses: int,
    rank: int = None,
):
    """
    Pillow render giống bag:

    1. HẠNG
    2. ELO
    3. THẮNG
    4. THUA

    Background ngoài hoàn toàn transparent.
    """

    # ========================================================
    # TRANSPARENT IMAGE
    # ========================================================

    img = Image.new(
        "RGBA",
        (
            WIDTH,
            HEIGHT,
        ),
        TRANSPARENT,
    )

    draw = ImageDraw.Draw(
        img
    )

    # ========================================================
    # HẠNG
    # ========================================================

    if rank is not None:
        rank_value = f"#{rank}"
    else:
        rank_value = "—"

    draw_stat_card(
        draw,
        y=10,
        title="HẠNG",
        value=rank_value,
        accent=(
            "R",
            RANK_DARK,
            RANK_COLOR,
        ),
    )

    # ========================================================
    # ELO
    # ========================================================

    draw_stat_card(
        draw,
        y=125,
        title="ELO",
        value=f"{rating:,}",
        accent=(
            "E",
            ELO_DARK,
            ELO_COLOR,
        ),
    )

    # ========================================================
    # THẮNG
    # ========================================================

    draw_stat_card(
        draw,
        y=240,
        title="THẮNG",
        value=f"{wins:,}",
        accent=(
            "W",
            WIN_DARK,
            WIN_COLOR,
        ),
    )

    # ========================================================
    # THUA
    # ========================================================

    draw_stat_card(
        draw,
        y=355,
        title="THUA",
        value=f"{losses:,}",
        accent=(
            "L",
            LOSS_DARK,
            LOSS_COLOR,
        ),
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
