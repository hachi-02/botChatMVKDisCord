# Kế hoạch: Minigame Gacha (thẻ nhân vật Genshin)

## ĐÃ CHỐT (từ user)
1. **Pity + 50/50:** CÓ.
2. **Capturing Radiance:** BỎ (mặc định, không phản đối).
3. **Cost:** 50đ/lần đơn, 450đ/10-pull (giảm 10%).
4. **Inventory:** B — lưu `gacha_cards`.
5. **Dup:** với B chỉ tăng `dup_count` (không hoàn điểm). Nếu muốn hoàn điểm -> báo (sang D).
6. **Tỷ lệ 5★:** 0.6% (giữ Genshin). 4★ = phần còn lại (~99.4%).
7. **3★ filler:** BỎ — 4★ là tier thấp nhất (sẽ rất phổ biến).
8. **Rolling GIF:** user tự tìm + cung cấp link trực tiếp.
9. **CHARACTER_POOL:** chờ user paste 22 thẻ (`Tên | link webp | 5L/5S/4`).

## CHARACTER_POOL (đã thu thập)
### 5★ LIMITED (5/5 ✅)
- Skirk | https://res.cloudinary.com/z2ffqaaf/image/upload/v1787824941/Skirk_Dynamic_Skin_hpmpgk.webp | 5L
- Raiden | https://res.cloudinary.com/z2ffqaaf/image/upload/v1787824880/Raiden_Shogun_Dynamic_Skin_xv5wvd.webp | 5L
- Nerfer | https://res.cloudinary.com/z2ffqaaf/image/upload/v1787824848/Nefer_Dynamic_Skin_xgth4j.webp | 5L
- Mavuika | https://res.cloudinary.com/z2ffqaaf/image/upload/v1787824744/Mavuika_Dynamic_Skin_wnti94.gif | 5L
- Furina | https://res.cloudinary.com/z2ffqaaf/image/upload/v1787824555/Furina_Dynamic_Skin_mrruy5.webp | 5L

### 5★ THƯỜNG (4/4 ✅)
- Mizuki | https://res.cloudinary.com/z2ffqaaf/image/upload/v1787824999/Yumemizuki_Mizuki_Dynamic_Skin_na6bna.webp | 5S
- Qiqi | https://res.cloudinary.com/z2ffqaaf/image/upload/v1787824906/Qiqi_Dynamic_Skin_fiasxj.webp | 5S
- Jean | https://res.cloudinary.com/z2ffqaaf/image/upload/v1787824652/Jean_Dynamic_Skin_qsanxc.webp | 5S
- Mona | https://res.cloudinary.com/z2ffqaaf/image/upload/v1787824777/Mona_Dynamic_Skin_dv0xsk.webp | 5S

## Còn thiếu để implement
- 13 nhân vật 4★.
- Link GIF "đang quay" (direct).

## ĐÃ CHỐT đầy đủ
1. Pity + 50/50: CÓ (soft 74, hard 90; 4★ đảm bảo mỗi 10 pull).
2. Capturing Radiance: BỎ.
3. Cost: 50đ/lần, 450đ/10-pull.
4. Inventory: B (lưu gacha_cards).
5. Dup: KHÔNG hoàn điểm, chỉ tăng dup_count ("vẫn tính thêm vô luôn").
6. Rate 5★: 0.6%; 4★ = phần còn lại.
7. 3★ filler: BỎ (4★ tier thấp nhất).
8. Rolling GIF: user tự tìm + cung cấp.
9. CHARACTER_POOL: chờ 22 thẻ từ user.

## Cơ chế chi tiết
- **Rarity:** 5★ (limited/standard) + 4★.
- **Roll 5★:** base 0.6%. Nếu `pity5 >= 74` → tỷ lệ tăng dần (soft pity, ~6% tại 74 → ~33% tại 90). Nếu `pity5 >= 90` → 100% (hard pity). Khi ra 5★: nếu `guarantee5` → bắt buộc LIMITED; else 50/50 LIMITED/STANDARD. Sau đó reset `pity5=0`, `guarantee5 = (not limited)` (thua 50/50 thì lần sau guaranteed).
- **Roll 4★:** mỗi pull, nếu `pity4 >= 9` (tức 10 pull chưa có 4★/5★) → forced 4★. Khi ra 4★/5★ reset `pity4=0`, else `pity4+1`. (Đảm bảo ≥1 thẻ 4★/5★ mỗi 10 pull.)
- **Chọn thẻ:** random uniform trong pool tương ứng (5L=5 thẻ, 5S=4 thẻ, 4★=13 thẻ).
- **10-pull:** `chị cá gacha 10`, cost 450, áp dụng pity chung.

## Data model (Neon)
- `gacha_state(user_id BIGINT PK, pity5 INT DEFAULT 0, pity4 INT DEFAULT 0, guarantee5 BOOL DEFAULT FALSE)`
- `gacha_cards(user_id BIGINT, char_key TEXT, rarity TEXT, dup_count INT DEFAULT 1, first_at TIMESTAMPTZ, PRIMARY KEY(user_id, char_key))`

## Files
- `config.py`: `GACHA_KEYWORDS=["gacha","quay","roll"]`, `GACHA_COST=50`, `GACHA_COST10=450`, `PITY_5_HARD=90`, `PITY_5_SOFT=74`, `PITY_4=10`, `RATE_5=0.006`, `RATE_50_50=0.5`, `GACHA_ROLL_GIF="<user cung cấp>"`, `CHARACTER_POOL=[{key,name,url,rarity}]` (22 entries).
- `db.py`: `spend_points(uid,amt)->bool`, `get_state(uid)`, `set_state(...)`, `add_card(uid,key,rarity)`, `get_collection(uid)`.
- `gacha.py` (mới): `roll_one(state)`, `handle_gacha(message,bot)`.
- `bot.py`: import, route `is_gacha` (parse "10"), gọi `handle_gacha`.

## Flow `handle_gacha`
1. parse `n = 10` nếu có "10" else 1; cost = GACHA_COST10 if n==10 else GACHA_COST*n.
2. nếu `get_points < cost` → reply thiếu điểm.
3. `spend_points`.
4. lặp n: cập nhật pity; roll rarity; resolve 5★ limited/standard; pick card; mark NEW/DUP.
5. gửi embed "đang quay" (GACHA_ROLL_GIF) → `await asyncio.sleep(2.5)` → gửi n embed kết quả (`set_image(url)`, màu 5★=vàng 0xFFD700, 4★=tím 0x9B59B6, footer MỚI / TRÙNG xN).
6. lưu `gacha_state` + `gacha_cards`.

## Lệnh xem collection (khi B)
- `chị cá sở hữu` / `chị cá collection` → embed nhóm theo rarity + danh sách tên + dup_count.
