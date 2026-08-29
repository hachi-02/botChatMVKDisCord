# =============================================
# features/activity.py
# Theo dõi "độ im lặng" của server và tự hỏi thăm khi vắng tin quá lâu.
# Tách từ bot.py. Nhận `bot` qua tham số, không import bot (tránh circular import).
# =============================================

import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

import discord

from config import (
    IDLE_HOURS,           # Số giờ im lặng để coi là "vắng" (mặc định 4.5h)
    IDLE_CHECK_INTERVAL,  # Chu kỳ kiểm tra (giây)
    IDLE_MAX_PER_DAY,     # Số lần hỏi thăm tối đa mỗi ngày mỗi server
    IDLE_SCAN_LIMIT,      # Số tin tối đa quét khi khởi động
    IDLE_CHANNEL_NAMES,   # Tên kênh để gửi câu hỏi thăm (vd: ["chat-chit"])
)
from ai import generate_ask   # Sinh câu hỏi thăm ngẫu nhiên qua AI

# Lần cuối có tin người thật (không tính bot): theo guild.id và channel.id
guild_last_human = {}
channel_last_human = {}
# Ngày đã hỏi thăm + số lần hỏi trong ngày đó (giới hạn IDLE_MAX_PER_DAY)
idle_sent_dates = {}
# Thời điểm lần cuối đã gửi câu hỏi thăm (tránh gửi lại quá dày)
idle_last_sent = {}


# Ghi nhận "có hoạt động người thật" — được gọi ở đầu on_message.
def note_activity(message):
    now = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))

    # Luôn cập nhật theo server (để biết cả server có im không)
    guild_last_human[message.guild.id] = now
    # Chỉ tính kênh text (bot tương tác ở đó), KHÔNG tính kênh thoại
    if isinstance(message.channel, discord.TextChannel):
        channel_last_human[message.channel.id] = now


# Khi bot mới khởi động: quét lịch sử các kênh text để suy ra server "đang im" từ trước.
# Đăng ký trong on_ready: bot.loop.create_task(scan_server_history(bot))
async def scan_server_history(bot):
    await bot.wait_until_ready()
    for guild in bot.guilds:
        try:
            last = None
            for ch in guild.text_channels:
                try:
                    # Đọc các tin gần nhất (bỏ qua tin của bot)
                    async for m in ch.history(limit=IDLE_SCAN_LIMIT):
                        if m.author == bot.user:
                            continue
                        if last is None or m.created_at > last:
                            last = m.created_at   # tin mới nhất của toàn server
                        cur = channel_last_human.get(ch.id)
                        if cur is None or m.created_at > cur:
                            channel_last_human[ch.id] = m.created_at
                except Exception:
                    continue   # Kênh không truy cập được -> bỏ qua
            if last is not None and (
                guild_last_human.get(guild.id) is None
                or last > guild_last_human[guild.id]
            ):
                guild_last_human[guild.id] = last
        except Exception as e:
            print(f"LỖI SCAN HISTORY {guild.name}: {type(e).__name__}: {e}", flush=True)


# Vòng lặp nền: mỗi IDLE_CHECK_INTERVAL giây, kiểm tra từng server.
# Nếu im >= IDLE_HOURS và chưa hỏi quá giới hạn -> AI tự gửi 1 câu hỏi thăm.
# Đăng ký trong on_ready: bot.loop.create_task(idle_checker(bot))
async def idle_checker(bot):
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            now = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))
            today = now.date()
            for guild in bot.guilds:
                last = guild_last_human.get(guild.id)
                if last is None:
                    continue   # Chưa có dữ liệu (server mới, chưa quét được)

                # Số giờ server im lặng
                idle = (now - last).total_seconds() / 3600
                if idle < IDLE_HOURS:
                    continue   # Chưa đủ im -> bỏ

                # Tránh gửi lại quá sớm sau lần hỏi trước
                if idle_last_sent.get(guild.id) is not None and \
                        (now - idle_last_sent[guild.id]).total_seconds() / 3600 < IDLE_HOURS:
                    continue

                # Kiểm tra giới hạn lượt hỏi /ngày
                sent_day, sent_count = idle_sent_dates.get(guild.id, (None, 0))
                if sent_day != today:
                    sent_count = 0   # Qua ngày mới -> reset lượt
                if sent_count >= IDLE_MAX_PER_DAY:
                    continue

                # Tìm kênh đích (tên nằm trong IDLE_CHANNEL_NAMES) thuộc loại text
                target = discord.utils.find(
                    lambda c: isinstance(c, discord.TextChannel)
                    and c.name.casefold() in [n.casefold() for n in IDLE_CHANNEL_NAMES],
                    guild.text_channels,
                )
                if target is None:
                    continue

                # Kiểm tra bot có quyền gửi tin ở kênh đó không
                perms = target.permissions_for(guild.me)
                if not (perms.send_messages and perms.view_channel):
                    continue

                # Sinh câu hỏi thăm qua AI (tên server + số giờ im lặng)
                text = generate_ask(guild.name, idle)
                if not text:
                    continue
                if len(text) > 1900:   # Giới hạn độ dài tin nhắn Discord
                    text = text[:1897] + "..."

                await target.send(text)

                # Lưu lại để không gửi quá nhiều / quá dày
                idle_last_sent[guild.id] = now
                idle_sent_dates[guild.id] = (today, sent_count + 1)
                print(f"IDLE ASK → {guild.name}: {text}", flush=True)
        except Exception as e:
            print(f"LỖI IDLE_CHECKER: {type(e).__name__}: {e}", flush=True)
        await asyncio.sleep(IDLE_CHECK_INTERVAL)
