from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from pilow_image.bag_pilow.renderer import (
    WIDTH,
    WHITE,
    GRAY,
    CARD,
    TRANSPARENT,
    get_font,
    rounded,
    draw_center_vertical,
    draw_right_center,
)

# ============================================================
# CONFIG
# ============================================================

HEADER_HEIGHT = 96
ROW_HEIGHT = 104
ROW_GAP = 12
MARGIN_TOP = 10
MARGIN_BOTTOM = 10
ROW_Y_OFFSET = 14

CIRCLE_BG = (43, 43, 43, 255)
ACCENT = (155, 89, 182, 255)


# ============================================================
# FONT / EMOJI
# ============================================================

_emoji_fonts = {}


def _get_emoji_font(size: int):
    if size not in _emoji_fonts:
        path = Path(r"C:\Windows\Fonts\seguiemj.ttf")
        try:
            _emoji_fonts[size] = ImageFont.truetype(str(path), size)
        except (OSError, IOError):
            _emoji_fonts[size] = get_font(size, True)
    return _emoji_fonts[size]


# ============================================================
# TÊN DANH MỤC -> (emoji, nhãn)
# ============================================================

_CATEGORY_INFO = {
    "🏆": "NÓI NHIỀU NHẤT",
    "📉": "NÓI ÍT NHẤT",
    "⚡": "TĂNG XP NHIỀU NHẤT",
    "💬": "KÊNH SÔI ĐỘNG NHẤT",
}


def _split_category(display: str):
    """Tách emoji mở đầu khỏi nhãn danh mục."""
    for emoji, label in _CATEGORY_INFO.items():
        if label in display.upper():
            return emoji, label
    # Fallback: emoji đầu tiên + phần còn lại
    first = display.strip().split(" ", 1)
    if len(first) == 2 and first[0]:
        return first[0], first[1].upper()
    return "", display.upper()


# ============================================================
# LAYOUT HELPERS
# ============================================================

def _calc_height(n_rows: int) -> int:
    return (
        MARGIN_TOP
        + HEADER_HEIGHT
        + ROW_Y_OFFSET
        + n_rows * (ROW_HEIGHT + ROW_GAP)
        - ROW_GAP
        + MARGIN_BOTTOM
    )


def _draw_header(draw, week_label, guild_name):
    x1 = 20
    x2 = WIDTH - 20

    rounded(
        draw,
        (x1, MARGIN_TOP, x2, MARGIN_TOP + HEADER_HEIGHT),
        14,
        fill=CARD,
        outline=ACCENT,
        width=2,
    )

    center_y = MARGIN_TOP + HEADER_HEIGHT // 2

    title_font = get_font(28, True)
    draw_center_vertical(draw, x1 + 50, center_y - 18, "BÁO CÁO THỐNG KÊ TUẦN", title_font, WHITE)

    sub_font = get_font(18, False)
    sub_text = f"{guild_name}  •  Tuần {week_label}"
    draw_center_vertical(draw, x1 + 50, center_y + 24, sub_text, sub_font, GRAY)

    fish_font = _get_emoji_font(40)
    draw_right_center(draw, x2 - 40, center_y, "🐟", fish_font, WHITE)


def _draw_row(img, draw, y, icon, label, value):
    x1 = 20
    x2 = WIDTH - 20

    rounded(
        draw,
        (x1, y, x2, y + ROW_HEIGHT),
        14,
        fill=CARD,
        outline=None,
        width=0,
    )

    center_y = y + ROW_HEIGHT // 2

    # Circle + emoji
    draw.ellipse(
        (x1 + 22, center_y - 32, x1 + 86, center_y + 32),
        fill=CIRCLE_BG,
    )
    emoji_font = _get_emoji_font(36)
    emoji_box = (
        x1 + 22,
        center_y - 32,
        x1 + 86,
        center_y + 32,
    )
    _draw_emoji_center(draw, emoji_box, icon, emoji_font)

    # Label
    label_font = get_font(23, True)
    draw_center_vertical(draw, x1 + 108, center_y, label, label_font, WHITE)

    # Value (phải)
    value_font = get_font(26, True)
    draw_right_center(draw, x2 - 25, center_y, value, value_font, WHITE)


def _draw_emoji_center(draw, box, text, font):
    x1, y1, x2, y2 = box
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = x1 + (x2 - x1 - tw) / 2 - bbox[0]
    y = y1 + (y2 - y1 - th) / 2 - bbox[1]
    draw.text((x, y), text, font=font, fill=(235, 235, 235, 255), embedded_color=True)


# ============================================================
# MAIN
# ============================================================

async def create_weekly_report_card(
    week_label: str,
    guild_name: str,
    rows,
):
    """
    Pillow render báo cáo thống kê tuần theo phong cách bag/daily.

    rows: list[(display_danh_mục, giá_trị)]
    """
    n_rows = len(rows) or 1
    height = _calc_height(n_rows)

    img = Image.new("RGBA", (WIDTH, height), TRANSPARENT)
    draw = ImageDraw.Draw(img)

    _draw_header(draw, week_label, guild_name)

    if rows:
        y = MARGIN_TOP + HEADER_HEIGHT + ROW_Y_OFFSET
        for display, value in rows:
            icon, label = _split_category(display)
            _draw_row(img, draw, y, icon, label, value)
            y += ROW_HEIGHT + ROW_GAP
    else:
        y = MARGIN_TOP + HEADER_HEIGHT + ROW_Y_OFFSET
        rounded(
            draw,
            (20, y, WIDTH - 20, y + ROW_HEIGHT),
            14,
            fill=CARD,
            outline=None,
            width=0,
        )
        draw_center_vertical(
            draw,
            108,
            y + ROW_HEIGHT // 2,
            "Chưa có dữ liệu",
            get_font(24, True),
            GRAY,
        )

    output = io.BytesIO()
    img.save(output, format="PNG", optimize=True)
    output.seek(0)
    return output
