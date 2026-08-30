from __future__ import annotations

import io

from PIL import Image, ImageDraw

from pilow_image.bag_pilow.renderer import (
    WIDTH,
    TRANSPARENT,
    draw_xp_card,
)


# ============================================================
# CANVAS (chỉ 1 card XP -> thấp)
# ============================================================

CARD_GAP = 115          # giống bag
CARD_HEIGHT = 100       # giống bag

HEIGHT = 130            # 100 card + đệm


# ============================================================
# MAIN
# ============================================================

async def create_levelup_card(
    author,
    level: int,
    xp: int,
    prog: int,
    points_per_level: int = 100,
):
    """
    Pillow render chỉ dùng thanh XP bar (giống card XP của bag):

    - Dòng "LEVEL n" (trái) + "xp / max XP" (phải)
    - Thanh XP điền theo tiến độ trong cấp

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
    # XP CARD (LEVEL + thanh XP)
    # ========================================================

    draw_xp_card(
        draw,
        y=10,
        level=level,
        current_xp=prog,
        max_xp=points_per_level,
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
