# =============================================
# features/report.py
# Báo cáo thống kê tuần tự động (Chủ nhật 20:00 giờ VN) vào kênh chat-chit.
# Hiển thị dạng bảng kẻ (kiểu Excel): 1 bên danh mục, 1 bên người đứng đầu.
# Tách từ bot.py. Nhận `bot` qua tham số, không import bot (tránh circular import).
# =============================================

import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import discord

from pilow_image.report_pilow import create_weekly_report_card

from config import (
    REPORT_WEEKDAY,
    REPORT_HOUR,
    REPORT_MINUTE,
    REPORT_CHANNEL_NAMES,
    REPORT_CHECK_INTERVAL,
    REPORT_KEEP_DAYS,
)
from db import (
    get_week_top_msg,
    get_week_bottom_msg,
    get_week_top_channel,
    get_all_xp,
    get_xp_snapshot,
    save_xp_snapshot,
    cleanup_msg_log,
)

# Đánh dấu (guild_id -> (ISO week, ) đã gửi) để tránh gửi lặp trong cùng tuần.
sent_weeks = {}


def _week_start(now: datetime) -> datetime:
    """Mốc đầu tuần (Chủ nhật 00:00 giờ VN) của tuần chứa `now`."""
    days_since_sunday = (now.weekday() - REPORT_WEEKDAY) % 7
    start = (now - timedelta(days=days_since_sunday)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return start


def _fmt_count(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def _choose_channel(guild):
    """Chọn kênh gửi báo cáo: kênh nào tên nằm trong REPORT_CHANNEL_NAMES (text)."""
    for name in REPORT_CHANNEL_NAMES:
        ch = discord.utils.find(
            lambda c: isinstance(c, discord.TextChannel)
            and c.name.casefold() == name.casefold(),
            guild.text_channels,
        )
        if ch and ch.permissions_for(guild.me).send_messages:
            return ch
    # Fallback: kênh text đầu tiên bot gửi được
    return discord.utils.find(
        lambda c: c.permissions_for(guild.me).send_messages,
        guild.text_channels,
    )


async def _person_name(bot, guild, user_id):
    """Trả tên hiển thị của user (cache qua member/fetch). Fallback id."""
    member = guild.get_member(user_id)
    if member:
        return member.display_name or member.name
    try:
        user = await bot.fetch_user(user_id)
        return user.display_name or user.name
    except Exception:
        return f"<@{user_id}>"


async def generate_weekly_report(bot, guild):
    """Tạo báo cáo tuần cho 1 server và gửi vào kênh phù hợp."""
    now = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))
    start = _week_start(now)

    top_msg = await get_week_top_msg(guild.id, start)
    bottom_msg = await get_week_bottom_msg(guild.id, start)
    top_ch = await get_week_top_channel(guild.id, start)

    # Tính delta XP: XP hiện tại - snapshot lần trước, chọn người tăng nhiều nhất
    current_xp = await get_all_xp(guild.id)
    prev_snap = await get_xp_snapshot(guild.id)
    xp_leader = None
    if prev_snap:
        best_uid, best_delta = None, -1
        for uid, xp in current_xp.items():
            delta = xp - prev_snap.get(uid, xp)
            if delta > best_delta:
                best_delta, best_uid = delta, uid
        if best_uid is not None and best_delta > 0:
            xp_leader = (best_uid, best_delta)

    rows = []

    if top_msg:
        name = await _person_name(bot, guild, top_msg["user_id"])
        rows.append(("🏆 Nói nhiều nhất", f"{name} ({_fmt_count(top_msg['count'])} tin)"))

    if bottom_msg and not (top_msg and top_msg["user_id"] == bottom_msg["user_id"]):
        name = await _person_name(bot, guild, bottom_msg["user_id"])
        rows.append(("📉 Nói ít nhất", f"{name} ({_fmt_count(bottom_msg['count'])} tin)"))

    if xp_leader:
        uid, delta = xp_leader
        name = await _person_name(bot, guild, uid)
        rows.append(("⚡ Tăng XP nhiều nhất", f"{name} (+{_fmt_count(delta)} XP)"))

    if top_ch:
        channel = guild.get_channel(top_ch["channel_id"])
        if channel is None:
            try:
                channel = await bot.fetch_channel(top_ch["channel_id"])
            except Exception:
                channel = None
        if channel is not None:
            ch_name = channel.mention
        else:
            ch_name = "Kênh đã bị xóa"
        rows.append(("💬 Kênh sôi động nhất", f"{ch_name} ({_fmt_count(top_ch['count'])} tin)"))

    week_label = start.strftime("%d/%m/%Y")

    image = await create_weekly_report_card(
        week_label=week_label,
        guild_name=guild.name,
        rows=rows,
    )

    e = discord.Embed(
        title="📊 BÁO CÁO THỐNG KÊ TUẦN 🐟",
        color=0x9B59B6,
    )
    if bot.user:
        e.set_author(name="Chị Cá 🐟", icon_url=bot.user.display_avatar.url)
    e.set_image(url="attachment://report.png")
    e.set_footer(text=f"Thống kê từ {week_label} • Chúc em 1 tuần mới vui vẻ 💙")

    file = discord.File(image, filename="report.png")

    channel = _choose_channel(guild)
    if channel is None:
        return
    await channel.send(embed=e, file=file)

    # Chụp XP hiện tại để tuần sau tính delta + dọn msg_log cũ
    await save_xp_snapshot(guild.id, current_xp)
    await cleanup_msg_log(REPORT_KEEP_DAYS)


async def weekly_report_checker(bot):
    """Vòng lặp nền: mỗi REPORT_CHECK_INTERVAL giây, kiểm tra có cần gửi báo cáo tuần."""
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            now = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))
            is_sunday = now.weekday() == REPORT_WEEKDAY
            past_hour = (now.hour, now.minute) >= (REPORT_HOUR, REPORT_MINUTE)
            week_key = now.isocalendar()[:2]  # (năm, tuần ISO)

            if is_sunday and past_hour:
                for guild in bot.guilds:
                    if sent_weeks.get(guild.id) == week_key:
                        continue
                    try:
                        await generate_weekly_report(bot, guild)
                        sent_weeks[guild.id] = week_key
                        print(f"REPORT → {guild.name} đã gửi báo cáo tuần 🐟", flush=True)
                    except Exception as e:
                        print(
                            f"LỖI REPORT {guild.name}: {type(e).__name__}: {e}",
                            flush=True,
                        )
            else:
                # Không phải thời điểm gửi -> reset dấu đã gửi (sang tuần mới)
                for gid in list(sent_weeks):
                    if sent_weeks[gid] != week_key:
                        sent_weeks.pop(gid, None)
        except Exception as e:
            print(f"LỖI WEEKLY_CHECKER: {type(e).__name__}: {e}", flush=True)
        await asyncio.sleep(REPORT_CHECK_INTERVAL)
