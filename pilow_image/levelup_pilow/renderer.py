from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


# ============================================================
# BASE CONFIG (tự chủ, không import từ bag)
# ============================================================

WIDTH = 900
TRANSPARENT = (0, 0, 0, 0)

CARD = (42, 42, 42, 245)
WHITE = (235, 235, 235, 255)
XP_BACKGROUND = (55, 55, 55, 255)
XP_FILL = (75, 190, 110, 255)


def get_font(size: int, bold: bool = False):
    """Tìm font hệ thống (Windows/Linux) an toàn, không cần file custom."""
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


def rounded(draw, box, radius, fill, outline=None, width=0):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def draw_center_vertical(draw, x, center_y, text, font, fill):
    """Căn text chính xác theo chiều dọc (bỏ qua độ sâu của dấu)."""
    bbox = draw.textbbox((0, 0), text, font=font)
    text_height = bbox[3] - bbox[1]
    y = center_y - text_height / 2 - bbox[1]
    draw.text((x, y), text, font=font, fill=fill)


def draw_right_center(draw, x_right, center_y, text, font, fill):
    """Căn phải + căn giữa theo chiều dọc."""
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = x_right - text_width - bbox[0]
    y = center_y - text_height / 2 - bbox[1]
    draw.text((x, y), text, font=font, fill=fill)


# ============================================================
# XP CARD (LEVEL + thanh XP)
# ============================================================

def draw_xp_card(draw, y, level, current_xp, max_xp):
    x1 = 20
    x2 = WIDTH - 20

    height = 100

    # CARD
    rounded(draw, (x1, y, x2, y + height), 14, fill=CARD, outline=None, width=0)

    # LEVEL
    draw_center_vertical(
        draw,
        x1 + 25,
        y + 30,
        f"LEVEL {level}",
        get_font(28, True),
        WHITE,
    )

    # XP TEXT
    draw_right_center(
        draw,
        x2 - 25,
        y + 30,
        f"{current_xp:,} / {max_xp:,} XP",
        get_font(23, True),
        WHITE,
    )

    # XP BAR
    bar_x = x1 + 25
    bar_y = y + 55
    bar_width = x2 - x1 - 50
    bar_height = 22

    rounded(
        draw,
        (bar_x, bar_y, bar_x + bar_width, bar_y + bar_height),
        11,
        fill=XP_BACKGROUND,
    )

    ratio = max(0, min(current_xp / max_xp, 1)) if max_xp > 0 else 0
    fill_width = int(bar_width * ratio)
    if fill_width > 0:
        rounded(
            draw,
            (bar_x, bar_y, bar_x + fill_width, bar_y + bar_height),
            11,
            fill=XP_FILL,
        )


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

    HEIGHT = 130

    img = Image.new("RGBA", (WIDTH, HEIGHT), TRANSPARENT)
    draw = ImageDraw.Draw(img)

    draw_xp_card(
        draw,
        y=10,
        level=level,
        current_xp=prog,
        max_xp=points_per_level,
    )

    output = io.BytesIO()
    img.save(output, format="PNG", optimize=True)
    output.seek(0)
    return output
