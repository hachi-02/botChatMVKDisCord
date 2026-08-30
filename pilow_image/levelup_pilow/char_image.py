from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from config import (
    CHAR_MAX_LEVEL,
    LEVEL_HP_BONUS,
    LEVEL_ATK_BONUS,
    LEVEL_SPD_BONUS,
)

ICON_DIR = Path(__file__).resolve().parent.parent.parent / "assets" / "icon_for_game"
IMAGE_ICON_DIR = Path(__file__).resolve().parent.parent.parent / "assets" / "imageIcon"

ICON_ATTACK = ICON_DIR / "icon_attack.png"
ICON_HP = ICON_DIR / "icon_hp.png"
ICON_SPD = ICON_DIR / "icon_spd.png"
ICON_MORA = IMAGE_ICON_DIR / "Item_Mora.webp"

ICON_SIZE = 40


# ============================================================
# BASE CONFIG
# ============================================================

WIDTH = 900

TRANSPARENT = (0, 0, 0, 0)
CARD = (42, 42, 42, 245)
WHITE = (235, 235, 235, 255)

# ============================================================
# FONT
# ============================================================

def get_font(size: int, bold: bool = False):
    """Tìm font hệ thống Windows/Linux."""

    windows_fonts = Path(r"C:\Windows\Fonts")

    if bold:
        candidates = [
            windows_fonts / "segoeuib.ttf",
            windows_fonts / "segoeuisb.ttf",
            windows_fonts / "arialbd.ttf",
        ]
    else:
        candidates = [
            windows_fonts / "segoeui.ttf",
            windows_fonts / "arial.ttf",
        ]

    for path in candidates:
        if path.is_file():
            try:
                return ImageFont.truetype(str(path), size)
            except (OSError, IOError):
                continue

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
                return ImageFont.truetype(path, size)
            except (OSError, IOError):
                continue

    return ImageFont.load_default(size)


# ============================================================
# DRAW HELPERS
# ============================================================

def rounded(draw, box, radius, fill, outline=None, width=0):
    draw.rounded_rectangle(
        box,
        radius=radius,
        fill=fill,
        outline=outline,
        width=width,
    )


def draw_center_vertical(
    draw,
    x,
    center_y,
    text,
    font,
    fill,
):
    """Căn text chính xác theo chiều dọc."""

    bbox = draw.textbbox(
        (0, 0),
        text,
        font=font,
    )

    text_height = bbox[3] - bbox[1]

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


def draw_right_center(
    draw,
    x_right,
    center_y,
    text,
    font,
    fill,
):
    """Căn phải + căn giữa theo chiều dọc."""

    bbox = draw.textbbox(
        (0, 0),
        text,
        font=font,
    )

    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    x = x_right - text_width - bbox[0]

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
# CANVAS
# ============================================================

MARGIN_X = 20
GAP = 12

# Ô 1: Level + XP
BOX_1_H = 110

# Ô 2: ATK / HP / SPD nằm ngang
BOX_2_H = 68

# Ô 3: Tiền
BOX_3_H = 90

HEIGHT = (
    12
    + BOX_1_H
    + GAP
    + BOX_2_H
    + GAP
    + BOX_3_H
    + 12
)


# ============================================================
# COLORS
# ============================================================

XP_FILL = (92, 184, 138, 255)
XP_BG = (55, 55, 55, 255)

HP_FILL = (231, 76, 60, 255)
ATK_FILL = (241, 196, 15, 255)
SPD_FILL = (52, 152, 219, 255)

MORA_FILL = (210, 175, 80, 255)


# ============================================================
# COMMON CARD
# ============================================================

def _rounded_box(
    draw,
    y,
    h,
    x1=20,
    x2=WIDTH - 20,
    r=14,
):
    rounded(
        draw,
        (x1, y, x2, y + h),
        r,
        fill=CARD,
        outline=None,
        width=0,
    )


# ============================================================
# Ô 1: LEVEL + XP BAR
# ============================================================

def _box_level(
    draw,
    y,
    lvl,
    max_lvl,
):
    _rounded_box(
        draw,
        y,
        BOX_1_H,
    )

    # LEVEL
    draw_center_vertical(
        draw,
        MARGIN_X + 25,
        y + 28,
        f"Level {lvl}/{max_lvl}",
        get_font(30, True),
        WHITE,
    )

    # XP BAR
    bar_x = MARGIN_X + 25
    bar_y = y + 62

    bar_w = (
        WIDTH
        - MARGIN_X
        - 50
    )

    bar_h = 24

    pct = (
        lvl / max_lvl
        if max_lvl
        else 0
    )

    pct = max(
        0,
        min(pct, 1),
    )

    # Background
    rounded(
        draw,
        (
            bar_x,
            bar_y,
            bar_x + bar_w,
            bar_y + bar_h,
        ),
        12,
        fill=XP_BG,
    )

    # Fill
    if pct > 0:
        fill_w = int(
            bar_w * pct
        )

        rounded(
            draw,
            (
                bar_x,
                bar_y,
                bar_x + fill_w,
                bar_y + bar_h,
            ),
            12,
            fill=XP_FILL,
        )


# ============================================================
# Ô 2: ATK / HP / SPD NẰM NGANG
# ============================================================

_icon_cache = {}


def _get_icon(path: Path) -> Image.Image:
    """Load + resize icon nhỏ, có cache để không load lại mỗi lần vẽ."""
    if path in _icon_cache:
        return _icon_cache[path]
    try:
        img = Image.open(path).convert("RGBA").resize(
            (ICON_SIZE, ICON_SIZE),
            Image.LANCZOS,
        )
    except Exception:
        img = None
    _icon_cache[path] = img
    return img


def _draw_stat_pair(
    draw,
    center_x,
    center_y,
    title,
    value,
    icon_path=None,
):
    """
    Vẽ:
        ATK 100
        HP  1200
        SPD 8.5

    Kèm icon (nếu có) ở phía trước title.
    """

    title_font = get_font(
        28,
        True,
    )

    value_font = get_font(
        30,
        True,
    )

    title_bbox = draw.textbbox(
        (0, 0),
        title,
        font=title_font,
    )

    value_bbox = draw.textbbox(
        (0, 0),
        value,
        font=value_font,
    )

    title_width = (
        title_bbox[2]
        - title_bbox[0]
    )

    value_width = (
        value_bbox[2]
        - value_bbox[0]
    )

    gap = 10

    total_width = (
        title_width
        + gap
        + value_width
    )

    icon = _get_icon(icon_path) if icon_path else None
    if icon is not None:
        total_width += ICON_SIZE + 8

    start_x = (
        center_x
        - total_width / 2
    )

    # ICON
    if icon is not None:
        draw = _paste_icon(draw, icon, start_x, center_y)
        start_x += ICON_SIZE + 8

    # TITLE
    draw_center_vertical(
        draw,
        start_x,
        center_y,
        title,
        title_font,
        WHITE,
    )

    # VALUE
    draw_center_vertical(
        draw,
        start_x
        + title_width
        + gap,
        center_y,
        value,
        value_font,
        WHITE,
    )


def _paste_icon(draw, icon: Image.Image, x_left: float, center_y: int):
    """Dán icon căn giữa theo chiều dọc vào `center_y`."""
    img = draw._image
    paste_x = int(x_left)
    paste_y = int(center_y - ICON_SIZE / 2)
    img.paste(icon, (paste_x, paste_y), icon)
    return draw


def _box_stats(
    draw,
    y,
    atk,
    hp,
    spd,
):
    _rounded_box(
        draw,
        y,
        BOX_2_H,
    )

    center_y = (
        y
        + BOX_2_H // 2
    )

    # 3 vị trí ngang
    left_center = 170
    middle_center = 450
    right_center = 730

    

    # HP
    _draw_stat_pair(
        draw,
        left_center,
        center_y,
        "HP:",
        f"{hp}",
        ICON_HP,
    )

    # ATK
    _draw_stat_pair(
        draw,
        middle_center,
        center_y,
        "ATK:",
        f"{atk}",
        ICON_ATTACK,
    )

    # SPD
    _draw_stat_pair(
        draw,
        right_center,
        center_y,
        "SPD:",
        f"{spd:.1f}",
        ICON_SPD,
    )


# ============================================================
# Ô 3: TIỀN HIỆN CÓ
# ============================================================

def _box_money(
    draw,
    y,
    mora,
):
    _rounded_box(
        draw,
        y,
        BOX_3_H,
    )

    center_y = (
        y
        + BOX_3_H // 2
    )

    # TITLE
    draw_center_vertical(
        draw,
        MARGIN_X + 25,
        center_y,
        "TIỀN HIỆN CÓ",
        get_font(30, True),
        WHITE,
    )

    # MONEY (căn phải, có icon mora bên phải số tiền, nằm gọn trong card)
    money_text = f"{mora:,}"
    money_font = get_font(34, True)
    mbox = draw.textbbox((0, 0), money_text, font=money_font)
    money_width = mbox[2] - mbox[0]
    edge_right = WIDTH - MARGIN_X - 25
    icon = _get_icon(ICON_MORA)
    gap = 8
    if icon is not None:
        # Dời số tiền sang trái để nhường chỗ cho icon bên phải, vẫn nằm trong card
        money_right = edge_right - ICON_SIZE - gap
    else:
        money_right = edge_right
    draw_right_center(
        draw,
        money_right,
        center_y,
        money_text,
        money_font,
        MORA_FILL,
    )
    if icon is not None:
        icon_left = money_right + gap
        _paste_icon(
            draw,
            icon,
            icon_left,
            center_y,
        )


# ============================================================
# MAIN
# ============================================================

async def create_levelup_card_image(
    card: dict,
    lvl: int,
    mora: int = 0,
):
    """
    Pillow render cho màn nâng cấp thẻ.

    Gồm:

    1. Level x/90 + XP bar
    2. ATK / HP / SPD nằm ngang
       - Không icon
       - Không vòng tròn
       - Không chia thành 3 dòng
    3. Tiền hiện có
    """

    # ========================================================
    # TÍNH STAT THEO LEVEL
    # ========================================================

    hp = (
        card["hp"]
        + LEVEL_HP_BONUS * (lvl - 1)
    )

    atk = (
        card["atk"]
        + LEVEL_ATK_BONUS * (lvl - 1)
    )

    spd = (
        card["spd"]
        + LEVEL_SPD_BONUS * (lvl - 1)
    )

    # ========================================================
    # CREATE IMAGE
    # ========================================================

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
    # BOX 1 - LEVEL
    # ========================================================

    y = 12

    _box_level(
        draw,
        y,
        lvl,
        CHAR_MAX_LEVEL,
    )

    # ========================================================
    # BOX 2 - STATS
    # ========================================================

    y += (
        BOX_1_H
        + GAP
    )

    _box_stats(
        draw,
        y,
        hp,
        atk,
        spd,
    )

    # ========================================================
    # BOX 3 - MONEY
    # ========================================================

    y += (
        BOX_2_H
        + GAP
    )

    _box_money(
        draw,
        y,
        mora,
    )

    # ========================================================
    # EXPORT PNG
    # ========================================================

    output = io.BytesIO()

    img.save(
        output,
        format="PNG",
        optimize=True,
    )

    output.seek(0)

    return output