import asyncio
import random
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import discord

from config import (
    ROLE_ID,
    KEYWORDS,
    CHUI_KEYWORDS,
    PROVOCATION_KEYWORDS,
    SEARCH_KEYWORDS,
    PROACTIVE_CHANCE,
    MIN_MESSAGE_LENGTH,
    PROACTIVE_KEYWORDS,
    MODEL_NAME,
    MEMBER_KEYWORDS,
    POLL_KEYWORDS,
    REMIND_KEYWORDS,
    EVENT_KEYWORDS,
    EVENT_HELP_KEYWORDS,
    INVITE_KEYWORDS,
    SUMMARY_KEYWORDS,
    SUMMARY_LIMIT,
    SUMMARY_MAX,
    HELP_KEYWORDS,
    EVENT_REMIND_MINUTES,
    EVENT_DEFAULT_DURATION_MINUTES,
    DATABASE_URL,
    POINT_KEYWORDS,
    POINT_COOLDOWN,
    POINTS_PER_MSG,
    POINTS_PER_LEVEL,
    EMOJI_MAP,
    SHOW_KEYWORDS,
    TEST_CARD_IMG,
)
from ai import ai, get_system_prompt, clean_ai_response
from memory import add_message, get_history, remember_user, get_known_users
from search import search_web
from web_server import start_web_server
from db import init_db
from points import maybe_award_points, handle_points, EMBED_COLOR, LEVELUP_GIF

intents = discord.Intents.default()
intents.members = True
intents.presences = True
intents.message_content = True

bot = discord.Client(intents=intents)

remind_queue = []
event_queue = []

NUMBER_EMOJIS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

def _event_help_embed(bot):
    e = discord.Embed(title="📌 Tạo sự kiện", color=EMBED_COLOR)
    if bot.user:
        e.set_author(name="Chị Cá 🐟", icon_url=bot.user.display_avatar.url)
    e.add_field(
        name="Cú pháp",
        value="`chị cá tạo sự kiện Tên | thời gian | mô tả | địa điểm`",
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
        value="• `chị cá tạo sự kiện Sinh nhật | ngày mai 20h | mang bánh | voice chung`\n"
              "• `chị cá event Offline | 25/12 19h30` 🐟",
        inline=False,
    )
    return e


def _menu_embed(bot):
    e = discord.Embed(title="Menu Chị Cá", color=EMBED_COLOR)
    if bot.user:
        e.set_author(name="Chị Cá", icon_url=bot.user.display_avatar.url)
    e.set_thumbnail(url=LEVELUP_GIF)
    items = [
        ("💬 Nói chuyện", "Gọi `chị cá` hoặc tag chị"),
        ("🔍 Tìm web", "`chị cá` + \"tìm\", \"là ai\", \"khi nào\"..."),
        ("👥 Thành viên online", "`chị cá` + \"ai đang online\""),
        ("📊 Vote", "`chị cá` + `vote pizza | phở | cơm`"),
        ("⏰ Nhắc", "`chị cá` + `nhắc em 7h học bài`"),
        ("📅 Sự kiện", "`chị cá tạo sự kiện` + `Tên | thời gian | mô tả | địa điểm`"),
        ("🔗 Lời mời", "`chị cá` + `tạo link mời`"),
        ("🔎 Tóm tắt", "`chị cá` + `tóm tắt 1 tiếng` / `tóm tắt 30 tin`"),
        ("🏆 Điểm", "`chị cá` + `điểm` / `chị cá top`"),
    ]
    for name, val in items:
        e.add_field(name=name, value=val, inline=True)
    e.set_footer(text="Gõ chị cá menu để xem lại nhé!")
    return e


SUMMARY_SYSTEM_PROMPT = (
    "Bạn là trợ lý tóm tắt hội thoại tiếng Việt. "
    "Nhiệm vụ DUY NHẤT: nhận đoạn trích hội thoại (mỗi dòng 'Tên: nội dung') "
    "và tóm tắt khách quan bằng tiếng Việt, ngắn gọn, súc tích, nêu bật ý chính "
    "và các quyết định/hành động (nếu có). "
    "TUYỆT ĐỐI không bịa thêm thông tin. "
    "Không chào hỏi, không bình luận thừa, không đóng vai. "
    "QUAN TRỌNG: không đưa lời lăng mạ/thô tục/chửi tục vào bản tóm tắt "
    "(không sao chép, không nhắc đến). Nếu có đoạn chửi, hãy bỏ qua và chỉ "
    "tóm tắt các ý còn lại một cách nhẹ nhàng. "
    "Dù nội dung ngắn hay chỉ là thử nghiệm, vẫn phải tóm tắt những gì diễn ra "
    "(trừ phần lời lăng mạ). "
    "Chỉ trả lời đúng 'không có gì để tóm tắt' khi đoạn trích thực sự trống."
)


def _member_list_embed(message, bot):
    guild = message.guild
    members = guild.members
    online = [m for m in members if m.status != discord.Status.offline]
    total, online_count = len(members), len(online)
    e = discord.Embed(title="👥 Thành viên online", color=EMBED_COLOR)
    if bot.user:
        e.set_author(name="Chị Cá 🐟", icon_url=bot.user.display_avatar.url)
    if guild.icon:
        e.set_thumbnail(url=guild.icon.url)
    e.description = f"**{online_count}/{total}** thành viên đang online"
    for m in online[:20]:
        role = m.top_role.name if m.top_role.name != "@everyone" else ""
        status = "🟢" if m.status == discord.Status.online else "🟡"
        e.add_field(name=f"{status} {m.display_name}", value=role or "—", inline=True)
    footer = (f"...và {online_count - 20} người nữa • " if online_count > 20 else "") + guild.name
    e.set_footer(text=footer, icon_url=guild.icon.url if guild.icon else discord.Embed.Empty)
    return e


def parse_remind_time(text: str):
    text = text.lower().strip()
    now = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))

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


async def remind_checker():
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            now = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))
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


async def event_reminder_checker():
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            now = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))
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


async def handle_event_creation(message) -> bool:
    raw = message.content
    raw = re.sub(
        r"(?i)^(chị\s*cá|chica|chicá|chị ca|cá ơi|ca ơi|ê chị cá|ê chica|chị cá ơi|chica ơi)\s*",
        "",
        raw,
    ).strip()
    raw = re.sub(
        r"(?i)^(tạo sự kiện|tạo event|lên lịch|event|schedule)\s*", "", raw
    ).strip()

    if bot.user:
        raw = raw.replace(bot.user.mention, "")
        raw = raw.replace(f"<@{bot.user.id}>", "")
        raw = raw.replace(f"<@!{bot.user.id}>", "")
    for role in message.role_mentions:
        raw = raw.replace(role.mention, "")
    raw = raw.strip()

    content_lower = message.content.lower()
    is_help = any(kw in content_lower for kw in EVENT_HELP_KEYWORDS)

    if is_help or not raw:
        await message.channel.send(embed=_event_help_embed(bot), reference=message)
        return True

    if "|" not in raw:
        return False

    parts = [p.strip() for p in raw.split("|") if p.strip()]

    if len(parts) < 2:
        await message.channel.send(embed=_event_help_embed(bot), reference=message)
        return True

    name = parts[0]
    time_text = parts[1]
    description = parts[2] if len(parts) > 2 else ""
    location = parts[3] if len(parts) > 3 else ""

    start_time = parse_remind_time(time_text)
    now = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))
    if not start_time or start_time <= now:
        await message.channel.send(
            "Chị chưa hiểu thời gian sự kiện, hoặc thời gian đã qua!\n"
            "**Ví dụ thời gian:** `ngày mai 20h`, `25/12 19h30`, `7h`, `30 phút nữa` 🐟",
            reference=message,
        )
        return True

    end_time = start_time + timedelta(minutes=EVENT_DEFAULT_DURATION_MINUTES)

    guild = message.guild
    if not guild:
        return True

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
        location = "Online"

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
        event = await guild.create_scheduled_event(**kwargs)
    except Exception as e:
        print(f"LỖI CREATE EVENT: {type(e).__name__}: {e}", flush=True)
        await message.channel.send(
            f"Chị không tạo được sự kiện 😭 Lỗi: `{type(e).__name__}: {e}`",
            reference=message,
        )
        return True

    if entity_type == discord.EntityType.external:
        loc_text = location
    else:
        loc_text = channel.mention if channel else ""

    desc_text = f"\n📝 {description}" if description else ""

    await message.channel.send(
        f"✅ Đã tạo sự kiện **{name}**!\n"
        f"🕒 Bắt đầu: {start_time.strftime('%H:%M %d/%m/%Y')}\n"
        f"📍 {loc_text}{desc_text}\n"
        f"🔔 Chị sẽ nhắc trước {EVENT_REMIND_MINUTES} phút nhé 🐟",
        reference=message,
    )

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


@bot.event
async def on_ready():
    print(f"Bot đã online: {bot.user}", flush=True)
    await start_web_server()
    bot.loop.create_task(remind_checker())
    bot.loop.create_task(event_reminder_checker())
    if not getattr(bot, "_db_inited", False):
        try:
            await init_db()
            bot._db_inited = True
        except Exception as e:
            print(f"LỖI INIT DB: {type(e).__name__}: {e}", flush=True)
    print("Chị Cá đã sẵn sàng 🐟", flush=True)


@bot.event
async def on_member_join(member):
    channel = member.guild.system_channel
    if channel:
        await channel.send(
            f"Chào em {member.mention} đến với server! 🐟 "
            f"Gọi chị Cá nếu cần gì nhé."
        )


@bot.event
async def on_message(message):

    print(f"NHẬN MESSAGE: {message.author}: {message.content}", flush=True)

    if message.author == bot.user:
        return

    if message.guild is None:
        return

    await maybe_award_points(message, bot)

    bot_mentioned = bot.user in message.mentions

    role_mentioned = any(role.id == ROLE_ID for role in message.role_mentions)

    content_lower = message.content.lower()

    addressed = (
        bot_mentioned
        or role_mentioned
        or any(kw in content_lower for kw in KEYWORDS)
    )

    is_general_help = addressed and any(
        kw in content_lower for kw in HELP_KEYWORDS
    )
    if is_general_help:
        await message.channel.send(embed=_menu_embed(bot), reference=message)
        return

    is_event = addressed and any(kw in content_lower for kw in EVENT_KEYWORDS)
    if is_event:
        handled = await handle_event_creation(message)
        if handled:
            return

    is_invite = addressed and any(kw in content_lower for kw in INVITE_KEYWORDS)
    if is_invite:
        try:
            invite = await message.channel.create_invite(
                max_age=604800,
                max_uses=0,
                unique=True,
                reason="Tạo lời mời bởi Chị Cá",
            )
            await message.channel.send(
                f"🔗 Lời mời vào server: {invite.url}\n(Link hiệu lực 7 ngày)",
                reference=message,
            )
        except Exception as e:
            print(f"LỖI CREATE INVITE: {type(e).__name__}: {e}", flush=True)
            await message.channel.send(
                "Chị không tạo được lời mời 😭 (bot thiếu quyền **Create Instant Invite** "
                "hoặc kênh không cho phép tạo invite).",
                reference=message,
            )
        return

    if addressed:
        is_member_list = any(kw in content_lower for kw in MEMBER_KEYWORDS)
        if is_member_list and message.guild:
            await message.channel.send(embed=_member_list_embed(message, bot), reference=message)
            return

        is_poll = any(kw in content_lower for kw in POLL_KEYWORDS)
        if is_poll:
            raw = message.content
            raw = re.sub(r"(?i)^(chị\s*cá|chica)\s*", "", raw).strip()
            raw = re.sub(r"(?i)^(poll|vote|bầu|bỏ\s*phiếu)\s*", "", raw).strip()
            options = [o.strip() for o in re.split(r"\||;", raw) if o.strip()]

            if len(options) < 2:
                await message.channel.send(
                    "Em viết chưa đúng format rồi. "
                    "Gõ: `poll pizza | phở | cơm` (phân tách bằng `|`) 🐟",
                    reference=message,
                )
                return

            if len(options) > 10:
                options = options[:10]

            poll_text = f"**POLL: {options[0]}**\n"
            for i, opt in enumerate(options):
                poll_text += f"{NUMBER_EMOJIS[i]} {opt}\n"
            sender = message.author.display_name or message.author.name
            poll_text += f"\nBỏ phiếu bằng cách react số tương ứng! ({sender} tạo)"

            poll_msg = await message.channel.send(poll_text)
            for i in range(len(options)):
                await poll_msg.add_reaction(NUMBER_EMOJIS[i])
            return

        is_remind = any(kw in content_lower for kw in REMIND_KEYWORDS)
        if is_remind:
            raw = message.content
            raw = re.sub(r"(?i)^(chị\s*cá|chica)\s*", "", raw).strip()
            raw = re.sub(
                r"(?i)^(nhắc\s*(t|tôi|em|e|tui)|remind)\s*", "", raw
            ).strip()

            now = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))
            remind_time = parse_remind_time(raw)
            if not remind_time:
                await message.channel.send(
                    "Chị chưa hiểu thời gian em muốn nhắc!\n"
                    "**📌 Ví dụ cách dùng:**\n"
                    "• `nhắc em 30 phút học bài`->`30 phút đếm ngược`\n"
                    "• `nhắc em 1 tiếng học bài`->`1 tiếng đếm ngược`\n"
                    "• `nhắc em 7h học bài`->`7:00 giờ cố định`\n"
                    "• `nhắc em ngày mai 8h30 dậy`\n"
                    "• `nhắc em 25/12 đi chợ`\n\n"
                    "💡Chỉ cần nói thời gian + việc cần nhắc là được!",
                    reference=message,
                )
                return

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
                task = "đến giờ rồi"

            remind_queue.append(
                {
                    "user_id": message.author.id,
                    "channel_id": message.channel.id,
                    "time": remind_time,
                    "task": task,
                }
            )

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
                reference=message,
            )
            return

    is_summary = addressed and any(kw in content_lower for kw in SUMMARY_KEYWORDS)
    if is_summary:
        raw = re.sub(r"^(chị\s*cá|chica)\s*", "", message.content, flags=re.I).strip()
        raw = raw.replace("tóm tắt", "", 1).strip()

        now = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))
        after = None
        limit = SUMMARY_LIMIT

        m_time = re.search(
            r"(\d+)\s*(phút|tiếng|giờ|ngày|phut|gio|ngay|p|h|hour|day|minute|minutes|min)",
            raw,
            re.I,
        )
        if m_time:
            n = int(m_time.group(1))
            u = m_time.group(2).lower()
            if u in ("phút", "phut", "minute", "minutes", "min", "p"):
                delta = timedelta(minutes=n)
            elif u in ("tiếng", "giờ", "gio", "hour", "h"):
                delta = timedelta(hours=n)
            else:
                delta = timedelta(days=n)
            after = now - delta
        else:
            m_count = re.search(r"(\d+)\s*(tin|tin nhắn|messages?)?", raw, re.I)
            if m_count:
                limit = min(int(m_count.group(1)), SUMMARY_MAX)

        try:
            if after:
                msgs = [
                    m
                    async for m in message.channel.history(
                        after=after, before=message, limit=SUMMARY_MAX
                    )
                ]
            else:
                msgs = [
                    m
                    async for m in message.channel.history(
                        limit=limit, before=message
                    )
                ]
        except Exception as e:
            print(f"LỖI SUMMARY FETCH: {type(e).__name__}: {e}", flush=True)
            await message.channel.send(
                "Chị không lấy được lịch sử kênh 😭 (bot cần quyền **Read Message History**).",
                reference=message,
            )
            return

        if not msgs and after is None:
            msgs = [m async for m in message.channel.history(limit=limit)]
            msgs = [m for m in msgs if m.id != message.id]

        msgs.reverse()
        transcript = "\n".join(
            f"{m.author.display_name}: {m.content}"
            for m in msgs
            if m.content or m.attachments or m.embeds
        )
        print(
            f"SUMMARY debug: raw={raw!r} after={after} limit={limit} "
            f"msgs={len(msgs)} transcript_len={len(transcript)}",
            flush=True,
        )
        if not transcript.strip():
            await message.channel.send(
                "Chị không thấy tin nhắn nào trước đó trong kênh này để tóm tắt 🐟",
                reference=message,
            )
            return

        system = SUMMARY_SYSTEM_PROMPT
        try:
            async with message.channel.typing():
                response = await asyncio.to_thread(
                    ai.chat.completions.create,
                    model=MODEL_NAME,
                    max_tokens=1500,
                    messages=[
                        {"role": "system", "content": system},
                        {
                            "role": "user",
                            "content": f"Tóm tắt cuộc hội thoại sau:\n\n{transcript}",
                        },
                    ],
                )
            summary = clean_ai_response(response.choices[0].message.content or "")
            if len(summary) > 2000:
                summary = summary[:1997] + "..."
            await message.channel.send(summary, reference=message)
        except Exception as e:
            print(f"LỖI SUMMARY: {type(e).__name__}: {e}", flush=True)
            await message.channel.send(
                "Chị tóm tắt hơi trục trặc rồi 😭", reference=message
            )
        return

    is_point = addressed and any(kw in content_lower for kw in POINT_KEYWORDS)
    if is_point:
        await handle_points(message, bot)
        return

    is_show = addressed and any(kw in content_lower for kw in SHOW_KEYWORDS)
    if is_show:
        e = discord.Embed(title="🎴 Test thẻ", color=EMBED_COLOR)
        e.set_image(url=TEST_CARD_IMG)
        await message.channel.send(embed=e, reference=message)
        return

    if not bot_mentioned and not role_mentioned:
        if not any(kw in content_lower for kw in KEYWORDS):

            is_proactive = (
                len(message.content) > MIN_MESSAGE_LENGTH
                and random.random() < PROACTIVE_CHANCE
                and any(kw in content_lower for kw in PROACTIVE_KEYWORDS)
            )

            if not is_proactive:
                return

            prompt = f"[TỰ ĐỘNG] {message.content}"
            sender_name = message.author.display_name or message.author.name

    is_chui = (
        bot_mentioned
        or role_mentioned
        or any(kw in content_lower for kw in KEYWORDS)
    ) and any(kw in content_lower for kw in CHUI_KEYWORDS)
    is_provoked = any(kw in content_lower for kw in PROVOCATION_KEYWORDS)

    prompt = message.content

    if bot.user:
        prompt = prompt.replace(bot.user.mention, "")
        prompt = prompt.replace(f"<@{bot.user.id}>", "")
        prompt = prompt.replace(f"<@!{bot.user.id}>", "")

    for role in message.role_mentions:
        prompt = prompt.replace(role.mention, "")

    prompt = prompt.strip()

    sender_name = message.author.display_name or message.author.name

    if is_chui:
        prompt = f"[CHỬI] {prompt}"
    elif is_provoked:
        prompt = f"[CHỌC GHẸO] {prompt}"

    is_member_list = any(kw in content_lower for kw in MEMBER_KEYWORDS)
    if is_member_list and message.guild:
        await message.channel.send(embed=_member_list_embed(message, bot), reference=message)
        return

    # =========================
    # TIM KIEM WEB
    # =========================

    is_search = any(kw in content_lower for kw in SEARCH_KEYWORDS)

    if is_search and not is_chui and not is_provoked:
        print(f"TÌM KIỂM: {prompt}", flush=True)
        search_results = await asyncio.to_thread(search_web, prompt)
        prompt = f"Thông tin tìm được trên mạng:\n{search_results}\n\nCâu hỏi của user: {prompt}"
        print(f"KẾT QUẢ TÌM KIỂM: {search_results[:200]}...", flush=True)

    if not prompt:
        await message.channel.send("M gọi Chị Cá đó hả? 🐟", reference=message)
        return

    channel_id = message.channel.id

    remember_user(message.author.id, sender_name)
    add_message(channel_id, "user", f"[{sender_name}]: {prompt}")

    try:
        print(f"GỬI AI: {prompt}", flush=True)

        system_prompt = get_system_prompt(sender_name, get_known_users())

        async with message.channel.typing():
            response = await asyncio.to_thread(
                ai.chat.completions.create,
                model=MODEL_NAME,
                reasoning_effort="default",
                max_tokens=4096,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt,
                    }
                ]
                + get_history(channel_id),
            )

        ai_message = response.choices[0].message
        finish_reason = response.choices[0].finish_reason
        print("USAGE:", response.usage, flush=True)

        print("AI RAW CONTENT:", repr(ai_message.content), flush=True)
        print("FINISH REASON:", finish_reason, flush=True)

        reasoning_content = getattr(ai_message, "reasoning_content", None)
        if reasoning_content:
            print("AI REASONING:", repr(reasoning_content), flush=True)

        answer = ai_message.content or ""
        answer = clean_ai_response(answer)

        # Map placeholder ngắn ([MEOW], [HEART], [SMILE], [ANGRY]) sang emoji thật
        for placeholder, emoji in EMOJI_MAP.items():
            answer = answer.replace(placeholder, emoji)

        # Fallback: fix nếu model lỡ viết sai format cũ dạng <:tên:số>
        answer = re.sub(r"\[:([a-z]+:\d+)\]", r"<:\1>", answer)
        answer = re.sub(r"(?<!<):([a-z]+):(\d+):", r"<:\1:\2>", answer)

        # Chỉ thêm "..." khi bị cắt THẬT SỰ do hết token (finish_reason == "length")
        if answer and finish_reason == "length":
            answer = answer.rstrip() + "..."

        print("AI CLEAN:", repr(answer), flush=True)

        if len(answer) > 2000:
            answer = answer[:1997] + "..."

        if not answer.strip():
            if finish_reason == "length":
                await message.channel.send(
                    "Câu này hơi dài, chị bị cắt ngang lúc đang trả lời rồi 😅 "
                    "em hỏi ngắn gọn lại giúp chị nhé.",
                    reference=message,
                )
            else:
                await message.channel.send(
                    "Chị Cá không biết trả lời sao 😅", reference=message
                )
            return

        print(f"AI: {answer}", flush=True)

        await message.channel.send(answer, reference=message)

        add_message(channel_id, "assistant", answer)

    except Exception as e:
        print(f"LỖI AI: {type(e).__name__}: {e}", flush=True)
        await message.channel.send("Chị Cá bị lỗi khi gọi AI rồi 😭", reference=message)