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
    draw_gem,
    draw_mora,
)


# ============================================================
# CANVAS (2 card -> thấp)
# ============================================================

CARD_GAP = 115          # giống bag
CARD_HEIGHT = 100       # giống bag

HEIGHT = 250            # 2 card: 10 + 100 + 115 + đệm


# ============================================================
# RESOURCE CARD (giống bag, nhưng value là chuỗi có dấu +)
# ============================================================

def draw_daily_resource_card(
    img,
    draw,
    y,
    title,
    value_text,
    icon_type,
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
    # ICON (icon thật của bag)
    # ========================================================

    if icon_type == "gem":
        draw_gem(
            img,
            draw,
            x1 + 50,
            center_y,
            31,
        )
    else:
        draw_mora(
            img,
            draw,
            x1 + 50,
            center_y,
            31,
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
    # VALUE (chuỗi, đã có dấu +)
    # ========================================================

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

async def create_daily_card(
    author,
    gems: int,
    mora: int,
    reward_gems: int,
    reward_mora: int,
):
    """
    Pillow render theo phong cách bag:

    1. NGUYÊN THẠCH (số nhận hôm nay, dấu +)
    2. MORA (số nhận hôm nay, dấu +)

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
    # NGUYÊN THẠCH (+số) — dùng icon gem thật như bag
    # ========================================================

    draw_daily_resource_card(
        img,
        draw,
        y=10,
        title="NGUYÊN THẠCH",
        value_text=f"+{reward_gems:,}",
        icon_type="gem",
    )

    # ========================================================
    # MORA (+số) — dùng icon mora thật như bag
    # ========================================================

    draw_daily_resource_card(
        img,
        draw,
        y=125,
        title="MORA",
        value_text=f"+{reward_mora:,}",
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
