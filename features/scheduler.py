# =============================================
# features/scheduler.py
# Quản lý "nhắc hẹn giờ" (remind) và "sự kiện" (scheduled event).
# Tách từ bot.py. Nhận `bot` qua tham số, KHÔNG import bot để tránh circular import.
# =============================================

import asyncio
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import discord

from config import (
    EVENT_HELP_KEYWORDS,
    EVENT_REMIND_MINUTES,
    EVENT_DEFAULT_DURATION_MINUTES,
)
from points import EMBED_COLOR

remind_queue = []   # Hàng đợi các lời nhắc: {user_id, channel_id, time, task}
event_queue = []    # Hàng đợi các sự kiện: {event_id, name, time, channel_id, notified}


# Tạo embed hướng dẫn cách dùng lệnh "tạo sự kiện".
def _event_help_embed(bot):
    e = discord.Embed(title="📌 Tạo sự kiện", color=EMBED_COLOR)
    if bot.user:
        e.set_author(name="Chị Cá 🐟", icon_url=bot.user.display_avatar.url)
    e.add_field(
        name="Cú pháp",
        value="`chica make event Tên | thời gian | mô tả | địa điểm`",
        inline=False,
    )
    e.add_field(name="Bắt buộc", value="**Tên** và **thời gian**", inline=True)
    e.add_field(name="Tuỳ chọn", value="**Mô tả** và **địa điểm**", inline=True)
    e.add_field(
        name="Ghi chú",
        value="Địa điểm trùng tên voice channel → tạo sự kiện trong kênh đó, "
              "không thì là sự kiện ngoài (`Online` mặc định).",
        inline=False,
    )
    e.add_field(
        name="Ví dụ",
        value="• `chica make event Sinh nhật | ngày mai 20h | mang bánh | voice chung`\n"
              "• `chica event Offline | 25/12 19h30` 🐟",
        inline=False,
    )
    return e


# Bóc tách thời điểm nhắc từ câu chữ tiếng Việt.
# Trả về một datetime (None nếu không hiểu). Ví dụ: "7h", "ngày mai 8h30",
# "25/12 19h30", "30 phút nữa", "1 tiếng", "2 ngày", "10 giây"...
def parse_remind_time(text: str):
    text = text.lower().strip()
    now = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))  # Múi giờ Việt Nam

    match = re.search(r"(?:ngày\s*mai|mai)\s+(\d{1,2})[h:](\d{2})", text)
    if match:
        hour, minute = int(match.group(1)), int(match.group(2))
        target = (now + timedelta(days=1)).replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )
        return target

    match = re.search(r"(?:ngày\s*mai|mai)\s+(\d{1,2})h\b", text)
    if match:
        hour = int(match.group(1))
        target = (now + timedelta(days=1)).replace(
            hour=hour, minute=0, second=0, microsecond=0
        )
        return target

    match = re.search(r"(\d{1,2})/(\d{1,2})\s+(\d{1,2})[h:](\d{2})", text)
    if match:
        day, month = int(match.group(1)), int(match.group(2))
        hour, minute = int(match.group(3)), int(match.group(4))
        target = now.replace(
            day=day, month=month, hour=hour, minute=minute, second=0, microsecond=0
        )
        if target <= now:
            target = target.replace(year=target.year + 1)
        return target

    match = re.search(r"(\d{1,2})/(\d{1,2})\s+(\d{1,2})h\b", text)
    if match:
        day, month = int(match.group(1)), int(match.group(2))
        hour = int(match.group(3))
        target = now.replace(
            day=day, month=month, hour=hour, minute=0, second=0, microsecond=0
        )
        if target <= now:
            target = target.replace(year=target.year + 1)
        return target

    match = re.search(r"(\d{1,2})/(\d{1,2})\b", text)
    if match:
        day, month = int(match.group(1)), int(match.group(2))
        target = now.replace(
            day=day, month=month, hour=0, minute=0, second=0, microsecond=0
        )
        if target <= now:
            target = target.replace(year=target.year + 1)
        return target

    match = re.search(r"(\d+)\s*(phút|minute|min|p)(?!\w)", text)
    if match:
        return now + timedelta(minutes=int(match.group(1)))

    match = re.search(r"(\d{1,2})\s*giờ\b", text)
    if match:
        hour = int(match.group(1))
        target = now.replace(hour=hour, minute=0, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        return target

    match = re.search(r"(\d+)\s*(tiếng|tieng|hour|hours)", text)
    if match:
        return now + timedelta(hours=int(match.group(1)))

    match = re.search(r"(\d+)\s*(ngày|day|ngay)", text)
    if match:
        return now + timedelta(days=int(match.group(1)))

    match = re.search(r"(\d+)\s*(giây|second|sec|s)", text)
    if match:
        return now + timedelta(seconds=int(match.group(1)))

    match = re.search(r"(\d{1,2})[h:](\d{2})", text)
    if match:
        hour, minute = int(match.group(1)), int(match.group(2))
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        return target

    match = re.search(r"(\d{1,2})h\b", text)
    if match:
        hour = int(match.group(1))
        target = now.replace(hour=hour, minute=0, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        return target

    return None


# Vòng lặp nền: cứ 10 giây kiểm tra remind_queue, gửi lời nhắc khi đến giờ.
# Đăng ký trong on_ready: bot.loop.create_task(remind_checker(bot))
async def remind_checker(bot):
    await bot.wait_until_ready()       # Chờ bot kết nối xong mới chạy
    while not bot.is_closed():
        try:
            now = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))
            # Lấy các lời nhắc đã "đến giờ"
            ready_reminds = [r for r in remind_queue if r["time"] <= now]
            for r in ready_reminds:
                remind_queue.remove(r)
                try:
                    user = await bot.fetch_user(r["user_id"])
                    channel = bot.get_channel(r["channel_id"])
                    if channel:
                        await channel.send(
                            f"{user.mention} Em ơi, chị nhắc nè: **{r['task']}** 🐟",
                        )
                except Exception as e:
                    print(f"LỖI REMIND: {e}", flush=True)
        except Exception as e:
            print(f"LỖI REMIND_CHECKER: {e}", flush=True)
        await asyncio.sleep(10)


# Vòng lặp nền: cứ 30 giây kiểm tra event_queue, nhắc @everyone trước giờ bắt đầu.
# Đăng ký trong on_ready: bot.loop.create_task(event_reminder_checker(bot))
async def event_reminder_checker(bot):
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            now = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))
            # Tìm sự kiện chưa được nhắc và còn trong khoảng "sắp bắt đầu"
            due = [
                e
                for e in event_queue
                if not e.get("notified")
                and timedelta(0)
                <= (e["time"] - now)
                <= timedelta(minutes=EVENT_REMIND_MINUTES)
            ]
            for e in due:
                e["notified"] = True
                channel = bot.get_channel(e["channel_id"])
                if channel:
                    await channel.send(
                        f"🔔 Sự kiện **{e['name']}** sắp bắt đầu trong khoảng "
                        f"{EVENT_REMIND_MINUTES} phút nữa! (@everyone) 🐟"
                    )
            event_queue[:] = [e for e in event_queue if e["time"] > now]
        except Exception as e:
            print(f"LỖI EVENT_REMINDER: {e}", flush=True)
        await asyncio.sleep(30)


# Xử lý lệnh "nhắc" (vd: `chị cá nhắc em 7h học bài`).
# Trả về True nếu đã xử lý hết (bot.py dừng lại), False nếu không phải lệnh này.
async def handle_remind(message, bot) -> bool:
    raw = message.content
    # Bỏ tiền tố "chị cá"/"chica" và từ "nhắc/remind" để lấy phần thời gian + việc
    raw = re.sub(r"(?i)^(chị\s*cá|chica)\s*", "", raw).strip()
    raw = re.sub(
        r"(?i)^(nhắc\s*(t|tôi|em|e|tui)|remind)\s*", "", raw
    ).strip()

    now = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))
    remind_time = parse_remind_time(raw)   # Bóc thời điểm nhắc
    if not remind_time:
        # Không hiểu thời gian -> gửi hướng dẫn
        await message.channel.send(
            "Chị chưa hiểu thời gian em muốn nhắc!\n"
            "**📌 Ví dụ cách dùng:**\n"
            "• `chica remind 30 phút học bài`->`30 phút đếm ngược`\n"
            "• `chica remind 1 tiếng học bài`->`1 tiếng đếm ngược`\n"
            "• `chica remind 7h học bài`->`7:00 giờ cố định`\n"
            "• `chica remind ngày mai 8h30 dậy`\n"
            "• `chica remind 25/12 đi chợ`\n\n"
            "💡Chỉ cần nói thời gian + việc cần nhắc là được!",
            reference=message, mention_author=False,
        )
        return True

    # Loại bỏ phần thời gian khỏi câu để giữ lại nội dung "việc cần nhắc"
    task = re.sub(
        r"(?:ngày\s*mai|mai)\s*\d+[h:]\d*\b", "", raw, flags=re.IGNORECASE
    ).strip()
    task = re.sub(
        r"\d+/\d+\s*\d+[h:]\d*\b", "", task, flags=re.IGNORECASE
    ).strip()
    task = re.sub(r"\d+/\d+\b", "", task, flags=re.IGNORECASE).strip()
    task = re.sub(
        r"\d+\s*(phút|giờ|ngày|giây|min|p|h|hour|day|second|tieng|tiếng)[\s:]*\d*",
        "",
        task,
        flags=re.IGNORECASE,
    ).strip()
    if not task:
        task = "đến giờ rồi"   # Không có việc nào -> nhắc mặc định

    # Đẩy lời nhắc vào hàng đợi để remind_checker xử lý
    remind_queue.append(
        {
            "user_id": message.author.id,
            "channel_id": message.channel.id,
            "time": remind_time,
            "task": task,
        }
    )

    # Tính khoảng thời gian còn lại để thông báo cho user
    diff = remind_time - now
    hours, remainder = divmod(int(diff.total_seconds()), 3600)
    minutes = remainder // 60
    time_str = ""
    if hours > 0:
        time_str += f"{hours} tiếng "
    if minutes > 0:
        time_str += f"{minutes} phút"

    await message.channel.send(
        f"OK em, {time_str} nữa chị sẽ nhắc: **{task}** 🐟",
        reference=message, mention_author=False,
    )
    return True


# Xử lý lệnh "tạo sự kiện" (vd: `chị cá tạo sự kiện Sinh nhật | ngày mai 20h | mô tả | địa điểm`).
# Trả về True nếu đã xử lý hết, False nếu không phải lệnh tạo sự kiện (thiếu "|").
async def handle_event_creation(message, bot) -> bool:
    raw = message.content
    # Bỏ tiền tố gọi bot ("chị cá", "chica", ...) và từ khóa "tạo sự kiện"
    raw = re.sub(
        r"(?i)^(chị\s*cá|chica|chicá|chị ca|cá ơi|ca ơi|ê chị cá|ê chica|chị cá ơi|chica ơi)\s*",
        "",
        raw,
    ).strip()
    raw = re.sub(
        r"(?i)^(make\s*event|tạo\s*sự\s*kiện|tạo\s*event|lên\s*lịch|event|schedule)\s*",
        "",
        raw,
    ).strip()

    if bot.user:
        # Xóa mention bot (<@id>) ra khỏi chuỗi để giữ phần nội dung
        raw = raw.replace(bot.user.mention, "")
        raw = raw.replace(f"<@{bot.user.id}>", "")
        raw = raw.replace(f"<@!{bot.user.id}>", "")
    for role in message.role_mentions:
        raw = raw.replace(role.mention, "")
    raw = raw.strip()

    content_lower = message.content.lower()
    # Nếu user chỉ muốn xem hướng dẫn (có từ trợ giúp) hoặc không có nội dung
    is_help = any(kw in content_lower for kw in EVENT_HELP_KEYWORDS)

    if is_help or not raw:
        await message.channel.send(embed=_event_help_embed(bot), reference=message, mention_author=False)
        return True

    # Dữ liệu sự kiện tách nhau bằng "|" -> nếu không có "|" thì không phải lệnh này
    if "|" not in raw:
        return False

    # Tách: Tên | thời gian | mô tả | địa điểm
    parts = [p.strip() for p in raw.split("|") if p.strip()]

    if len(parts) < 2:
        # Thiếu bắt buộc (Tên + thời gian) -> hiện hướng dẫn
        await message.channel.send(embed=_event_help_embed(bot), reference=message, mention_author=False)
        return True

    name = parts[0]
    time_text = parts[1]
    description = parts[2] if len(parts) > 2 else ""
    location = parts[3] if len(parts) > 3 else ""

    start_time = parse_remind_time(time_text)   # Bóc thời gian bắt đầu
    now = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))
    if not start_time or start_time <= now:
        # Thời gian không hiểu hoặc đã qua -> báo lỗi
        await message.channel.send(
            "Chị chưa hiểu thời gian sự kiện, hoặc thời gian đã qua!\n"
            "**Ví dụ thời gian:** `ngày mai 20h`, `25/12 19h30`, `7h`, `30 phút nữa` 🐟",
            reference=message, mention_author=False,
        )
        return True

    # Sự kiện kéo dài mặc định (giờ mặc định) tính từ lúc bắt đầu
    end_time = start_time + timedelta(minutes=EVENT_DEFAULT_DURATION_MINUTES)

    guild = message.guild
    if not guild:
        return True

    # Mặc định là sự kiện "ngoài" (external). Nếu địa điểm trùng tên voice channel
    # thì chuyển thành sự kiện trong kênh voice (entity_type = voice).
    entity_type = discord.EntityType.external
    channel = None
    if location:
        voice_channel = discord.utils.find(
            lambda c: c.name.casefold() == location.casefold(),
            guild.voice_channels,
        )
        if voice_channel:
            entity_type = discord.EntityType.voice
            channel = voice_channel
            location = ""

    if entity_type == discord.EntityType.external and not location:
        location = "Online"   # Sự kiện ngoài không có nơi thì để "Online"

    # Ghép tham số gọi API tạo sự kiện của Discord
    kwargs = dict(
        name=name,
        start_time=start_time,
        end_time=end_time,
        description=description or None,
        entity_type=entity_type,
        privacy_level=discord.PrivacyLevel.guild_only,
    )
    if entity_type == discord.EntityType.external:
        kwargs["location"] = location
        kwargs["channel"] = discord.utils.MISSING
    else:
        kwargs["channel"] = channel
        kwargs["location"] = discord.utils.MISSING

    try:
        # Gọi API Discord để tạo sự kiện trên server
        event = await guild.create_scheduled_event(**kwargs)
    except Exception as e:
        print(f"LỖI CREATE EVENT: {type(e).__name__}: {e}", flush=True)
        await message.channel.send(
            f"Chị không tạo được sự kiện 😭 Lỗi: `{type(e).__name__}: {e}`",
            reference=message, mention_author=False,
        )
        return True

    # Hiển thị embed tổng kết sự kiện vừa tạo
    if entity_type == discord.EntityType.external:
        loc_text = location
    else:
        loc_text = channel.mention if channel else ""

    desc = f"📝 {description}" if description else None
    e = discord.Embed(
        title=f"📅 {name}",
        description=desc,
        color=0x9B59B6,
    )
    if bot.user:
        e.set_author(name="Chị Cá 🐟", icon_url=bot.user.display_avatar.url)
    e.add_field(
        name="🕒 Bắt đầu",
        value=start_time.strftime("%H:%M %d/%m/%Y"),
        inline=True,
    )
    e.add_field(
        name="📍 Địa điểm",
        value=loc_text or "Online",
        inline=True,
    )
    e.add_field(
        name="🔔 Nhắc",
        value=f"Chị sẽ nhắc trước {EVENT_REMIND_MINUTES} phút nhé 🐟",
        inline=False,
    )
    e.set_footer(text=f"✅ Đã tạo sự kiện • {message.author.display_name} tạo")
    await message.channel.send(embed=e, reference=message, mention_author=False)

    # Lưu vào hàng đợi để event_reminder_checker nhắc trước giờ bắt đầu
    event_queue.append(
        {
            "event_id": event.id,
            "name": name,
            "time": start_time,
            "channel_id": message.channel.id,
            "notified": False,
        }
    )
    return True
