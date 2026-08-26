import asyncio
import random
import re
from datetime import datetime, timedelta

import discord

from ai import ai, clean_ai_response, get_system_prompt
from config import (
    CHUI_KEYWORDS,
    KEYWORDS,
    MEMBER_KEYWORDS,
    MIN_MESSAGE_LENGTH,
    MODEL_NAME,
    POLL_KEYWORDS,
    PROACTIVE_CHANCE,
    PROACTIVE_KEYWORDS,
    PROVOCATION_KEYWORDS,
    REMIND_KEYWORDS,
    ROLE_ID,
    SEARCH_KEYWORDS,
)
from memory import add_message, get_history, get_known_users, remember_user
from search import search_web
from web_server import start_web_server

intents = discord.Intents.default()
intents.members = True
intents.presences = True
intents.message_content = True

bot = discord.Client(intents=intents)

remind_queue = []

NUMBER_EMOJIS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]


def parse_remind_time(text: str):
    text = text.lower().strip()
    now = datetime.now()

    # 1. Dạng "ngày mai / mai" (ví dụ: mai 7h30, mai 7h, ngày mai 8:00)
    match = re.search(r"(?:ngày\s*mai|mai)\s+(\d{1,2})(?:[h:](\d{2}))?", text)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2)) if match.group(2) else 0
        target = (now + timedelta(days=1)).replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )
        return target

    # 2. Dạng ngày/tháng + giờ (ví dụ: 25/12 8h30, 25/12 8h)
    match = re.search(r"(\d{1,2})/(\d{1,2})\s+(\d{1,2})(?:[h:](\d{2}))?", text)
    if match:
        day, month = int(match.group(1)), int(match.group(2))
        hour = int(match.group(3))
        minute = int(match.group(4)) if match.group(4) else 0
        target = now.replace(
            day=day, month=month, hour=hour, minute=minute, second=0, microsecond=0
        )
        if target <= now:
            target = target.replace(year=target.year + 1)
        return target

    # 3. Dạng ngày/tháng (ví dụ: 25/12 - mặc định 00:00)
    match = re.search(r"(\d{1,2})/(\d{1,2})\b", text)
    if match:
        day, month = int(match.group(1)), int(match.group(2))
        target = now.replace(
            day=day, month=month, hour=0, minute=0, second=0, microsecond=0
        )
        if target <= now:
            target = target.replace(year=target.year + 1)
        return target

    # 4. Khoảng thời gian đếm ngược (phút, giờ, ngày, giây)
    match = re.search(r"(\d+)\s*(phút|minute|min|p)(?!\w)", text)
    if match:
        return now + timedelta(minutes=int(match.group(1)))

    match = re.search(r"(\d+)\s*(giờ|hour|hours|tieng|tiếng|h)(?!\w)", text)
    if match:
        return now + timedelta(hours=int(match.group(1)))

    match = re.search(r"(\d+)\s*(ngày|day|ngay)(?!\w)", text)
    if match:
        return now + timedelta(days=int(match.group(1)))

    match = re.search(r"(\d+)\s*(giây|second|sec|s)(?!\w)", text)
    if match:
        return now + timedelta(seconds=int(match.group(1)))

    # 5. Dạng giờ cố định trong ngày (ví dụ: 7h, 7:30, 19h)
    match = re.search(r"(\d{1,2})(?:[h:](\d{2}))?", text)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2)) if match.group(2) else 0
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        return target

    return None


async def remind_checker():
    await bot.wait_until_ready()
    while not bot.is_closed():
        now = datetime.now()
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
        await asyncio.sleep(10)


@bot.event
async def on_ready():
    print(f"Bot đã online: {bot.user}", flush=True)
    await start_web_server()
    bot.loop.create_task(remind_checker())
    print("Chị Cá đã sẵn sàng 🐟", flush=True)


@bot.event
async def on_member_join(member):
    channel = member.guild.system_channel
    if channel:
        await channel.send(
            f"Chào em {member.mention} đến với server! 🐟 Gọi chị Cá nếu cần gì nhé."
        )


@bot.event
async def on_message(message):
    print(f"NHẬN MESSAGE: {message.author}: {message.content}", flush=True)

    if message.author == bot.user:
        return

    if message.guild is None:
        return

    bot_mentioned = bot.user in message.mentions
    role_mentioned = any(
        role.id == ROLE_ID for role in message.role_mentions
    )
    content_lower = message.content.lower()

    # Kiểm tra xem bot có được gọi trực tiếp không
    is_keyword = any(kw in content_lower for kw in KEYWORDS)

    if not bot_mentioned and not role_mentioned and not is_keyword:
        # 1. Kiểm tra danh sách member
        is_member_list = any(kw in content_lower for kw in MEMBER_KEYWORDS)
        if is_member_list and message.guild:
            members = message.guild.members
            online = [m for m in members if m.status != discord.Status.offline]
            total = len(members)
            online_count = len(online)

            member_lines = []
            for m in online[:20]:
                role = (
                    m.top_role.name if m.top_role.name != "@everyone" else ""
                )
                status = "🟢" if m.status == discord.Status.online else "🟡"
                name = m.display_name
                member_lines.append(
                    f"{status} {name}" + (f" ({role})" if role else "")
                )

            result = f"**Thành viên đang online: {online_count}/{total}**\n"
            result += "\n".join(member_lines)
            if online_count > 20:
                result += f"\n...và {online_count - 20} người nữa"

            await message.channel.send(result, reference=message)
            return

        # 2. Tạo Poll
        is_poll = any(kw in content_lower for kw in POLL_KEYWORDS)
        if is_poll:
            raw = message.content
            raw = re.sub(r"(?i)^(chị\s*cá|chica)\s*", "", raw).strip()
            raw = re.sub(
                r"(?i)^(poll|vote|bầu|bỏ\s*phiếu)\s*", "", raw
            ).strip()
            options = [o.strip() for o in re.split(r"\||;", raw) if o.strip()]

            if len(options) < 2:
                await message.channel.send(
                    "Em viết chưa đúng format rồi. Gõ: `poll pizza | phở | cơm` (phân tách bằng `|`) 🐟",
                    reference=message,
                )
                return

            if len(options) > 10:
                options = options[:10]

            poll_text = f"**POLL: {options[0]}**\n"
            for i, opt in enumerate(options):
                poll_text += f"{NUMBER_EMOJIS[i]} {opt}\n"
            sender = message.author.display_name or message.author.name
            poll_text += (
                f"\nBỏ phiếu bằng cách react số tương ứng! ({sender} tạo)"
            )

            poll_msg = await message.channel.send(poll_text)
            for i in range(len(options)):
                await poll_msg.add_reaction(NUMBER_EMOJIS[i])
            return

        # 3. Đặt Reminder
        is_remind = any(kw in content_lower for kw in REMIND_KEYWORDS)
        if is_remind:
            raw = message.content
            raw = re.sub(r"(?i)^(chị\s*cá|chica)\s*", "", raw).strip()
            raw = re.sub(
                r"(?i)^(nhắc\s*(t|tôi|em|e|tui)|remind)\s*", "", raw
            ).strip()

            now = datetime.now()
            remind_time = parse_remind_time(raw)
            if not remind_time:
                await message.channel.send(
                    "Em viết chưa rõ thời gian rồi. "
                    "Ví dụ: `nhắc t 30 phút học bài`, `remind 7h đi ngủ`, "
                    "`nhắc t ngày mai 8h30 dậy`, hoặc `nhắc t 25/12 đi chợ` 🐟",
                    reference=message,
                )
                return

            # Bóc tách Task sạch sẽ
            task = re.sub(
                r"(?:ngày\s*mai|mai)\s*\d+(?:[h:]\d*)?",
                "",
                raw,
                flags=re.IGNORECASE,
            ).strip()
            task = re.sub(
                r"\d+/\d+\s*\d+(?:[h:]\d*)?", "", task, flags=re.IGNORECASE
            ).strip()
            task = re.sub(r"\d+/\d+", "", task, flags=re.IGNORECASE).strip()
            task = re.sub(
                r"\d+\s*(phút|giờ|ngày|giây|min|p|h|hour|day|second|tieng|tiếng)(?!\w)",
                "",
                task,
                flags=re.IGNORECASE,
            ).strip()
            task = re.sub(
                r"\b\d{1,2}(?:[h:]\d{2})?\b", "", task, flags=re.IGNORECASE
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
                time_str += f"{hours} giờ "
            if minutes > 0 or hours == 0:
                time_str += f"{minutes} phút"

            await message.channel.send(
                f"OK em, {time_str} nữa chị sẽ nhắc: **{task}** 🐟",
                reference=message,
            )
            return

        # 4. Trả lời chủ động (Proactive)
        is_proactive = (
            len(message.content) > MIN_MESSAGE_LENGTH
            and random.random() < PROACTIVE_CHANCE
            and any(kw in content_lower for kw in PROACTIVE_KEYWORDS)
        )

        if not is_proactive:
            return

    # =========================
    # XỬ LÝ CHAT VỚI AI
    # =========================
    is_chui = any(kw in content_lower for kw in CHUI_KEYWORDS)
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

    # Tìm kiếm Web nếu có từ khóa
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

        answer = ai_message.content or ""
        answer = clean_ai_response(answer)

        # Fix emoji format thiếu <
        answer = re.sub(r"\[:([a-z]+:\d+)\]", r"<:\1>", answer)
        answer = re.sub(r"(?<!<)(:([a-z]+:\d+):)", r"<\1>", answer)

        # Fix response bị cắt giữa chừng
        emoji_pattern = re.compile(r"<:[a-z]+:\d+>$")
        if answer and not emoji_pattern.search(answer.rstrip()):
            last_line = answer.rstrip().split("\n")[-1]
            if len(last_line) < 50:
                answer = answer.rstrip() + "..."

        if len(answer) > 2000:
            answer = answer[:1997] + "..."

        if not answer.strip():
            if finish_reason == "length":
                await message.channel.send(
                    "Câu này hơi dài, chị bị cắt ngang lúc đang trả lời rồi 😅 em hỏi ngắn gọn lại giúp chị nhé.",
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
        await message.channel.send(
            "Chị Cá bị lỗi khi gọi AI rồi 😭", reference=message
        )