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
    draw_center_vertical,
    draw_right_center,
    draw_center,
)


# ============================================================
# CANVAS (bag: 3 card -> HEIGHT 390; pvp: 4 card -> cao hơn)
# ============================================================

CARD_GAP = 115          # giống bag (10 -> 125 -> 240)
CARD_HEIGHT = 100       # giống bag

HEIGHT = 470            # 4 card: 10 + 100 + 115*3 + đệm


# ============================================================
# COLORS (giữ phong cách bag, thêm màu riêng của PvP)
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
# STAT CARD (giống "resource card" của bag)
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

    center_y = (
        y + height // 2
    )

    # ========================================================
    # ICON BACKGROUND (vòng tròn như bag)
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
    # ICON (ký tự nổi bật theo loại stat)
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

    1. Status card: tên + thứ hạng + thanh win-rate
    2. ELO
    3. THẮNG (wins)
    4. THUA (losses)

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
    # HẠNG (giống các ô còn lại: icon tròn + tiêu đề + giá trị)
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
        accent=("R", RANK_DARK, RANK_COLOR),
    )

    # ========================================================
    # ELO
    # ========================================================

    draw_stat_card(
        draw,
        y=125,
        title="ELO",
        value=f"{rating:,}",
        accent=("E", ELO_DARK, ELO_COLOR),
    )

    # ========================================================
    # THẮNG
    # ========================================================

    draw_stat_card(
        draw,
        y=240,
        title="THẮNG",
        value=f"{wins:,}",
        accent=("W", WIN_DARK, WIN_COLOR),
    )

    # ========================================================
    # THUA
    # ========================================================

    draw_stat_card(
        draw,
        y=355,
        title="THUA",
        value=f"{losses:,}",
        accent=("L", LOSS_DARK, LOSS_COLOR),
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
