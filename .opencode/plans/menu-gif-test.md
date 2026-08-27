# Kế hoạch: Test GIF động trong menu Chị Cá

## Mục tiêu
Trong menu (`chị cá menu`), bỏ icon cá 🐟 và thay bằng GIF động bạn cung cấp, đặt bên trái chữ "Chị Cá" (author icon) để thử xem có chạy động không. Không đụng thẻ điểm cá nhân.

## Thay đổi

### 1. `points.py` — thêm hằng số GIF (nguồn chung cho cả thông báo sau này)
Sau dòng `EMBED_COLOR = 0x1ABC9C` (dòng 10), thêm:
```python
LEVELUP_GIF = "https://media.giphy.com/media/v1.Y2lkPWVjZjA1ZTQ3dzd6ZDF0ZnJ1aXRlMzc1ZzV2M29zdnVteGN2ODN3MXExZmszaDlwdyZlcD12MV9naWZzX3NlYXJjaCZjdD1n/sIYOpmEC16sWVQtOs3/giphy.gif"
```
(Đã kiểm tra: URL trả `200 image/gif`, 5.1 MB.)

### 2. `bot.py` — import hằng số
Dòng 43 đổi thành:
```python
from points import maybe_award_points, handle_points, EMBED_COLOR, LEVELUP_GIF
```

### 3. `bot.py` — sửa `_menu_embed` (dòng 83-101)
- Dòng 84: `e = discord.Embed(title="Menu Chị Cá", color=EMBED_COLOR)`  (bỏ 🐟)
- Dòng 86: `e.set_author(name="Chị Cá", icon_url=LEVELUP_GIF)`  (bỏ 🐟, thay avatar bot bằng GIF)

## Kiểm tra & triển khai
1. `python -m py_compile points.py bot.py`
2. Commit: `git add points.py bot.py && git commit -m "test(ui): thay icon cá bằng GIF động trong menu để test animation"`
3. `git push origin main`
4. Redeploy Render.
5. Gõ `chị cá menu` → xác nhận GIF có chạy động ở góc trái author.

## Ghi chú
- Bước này chỉ là thử nghiệm. Sau khi xác nhận GIF chạy được, đưa GIF vào thông báo lên cấp (`_award_and_notify` trong `points.py`) qua `e.set_thumbnail(url=LEVELUP_GIF)` (giữ nguyên avatar bot).
- Nếu muốn GIF nằm góc phải (thumbnail cạnh tiêu đề) thay vì author icon, dùng `e.set_thumbnail(url=LEVELUP_GIF)` và giữ avatar bot ở author.
