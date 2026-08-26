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
)
from ai import ai, get_system_prompt, clean_ai_response
from memory import add_message, get_history, remember_user, get_known_users
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

    bot_mentioned = bot.user in message.mentions

    role_mentioned = any(role.id == ROLE_ID for role in message.role_mentions)

    content_lower = message.content.lower()

    if not bot_mentioned and not role_mentioned:
        if not any(kw in content_lower for kw in KEYWORDS):

            is_member_list = any(kw in content_lower for kw in MEMBER_KEYWORDS)
            if is_member_list and message.guild:
                members = message.guild.members
                online = [m for m in members if m.status != discord.Status.offline]
                total = len(members)
                online_count = len(online)

                member_lines = []
                for m in online[:20]:
                    role = m.top_role.name if m.top_role.name != "@everyone" else ""
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

            is_proactive = (
                len(message.content) > MIN_MESSAGE_LENGTH
                and random.random() < PROACTIVE_CHANCE
                and any(kw in content_lower for kw in PROACTIVE_KEYWORDS)
            )

            if not is_proactive:
                return

            prompt = f"[TỰ ĐỘNG] {message.content}"
            sender_name = message.author.display_name or message.author.name

            is_chui = False
            is_provoked = False

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

    is_member_list = any(kw in content_lower for kw in MEMBER_KEYWORDS)
    if is_member_list and message.guild:
        members = message.guild.members
        online = [m for m in members if m.status != discord.Status.offline]
        total = len(members)
        online_count = len(online)

        member_lines = []
        for m in online[:20]:
            role = m.top_role.name if m.top_role.name != "@everyone" else ""
            status = "🟢" if m.status == discord.Status.online else "🟡"
            name = m.display_name
            member_lines.append(f"{status} {name}" + (f" ({role})" if role else ""))

        result = f"**Thành viên đang online: {online_count}/{total}**\n"
        result += "\n".join(member_lines)
        if online_count > 20:
            result += f"\n...và {online_count - 20} người nữa"

        await message.channel.send(result, reference=message)
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

        # Fix emoji format thiếu <
        answer = re.sub(r"\[:([a-z]+:\d+)\]", r"<:\1>", answer)
        answer = re.sub(r"(?<!<)(:([a-z]+:\d+):)", r"<\1>", answer)

        # Fix response bi cut giua chung — chi them ... neu KHONG ket thuc bang custom emoji
        emoji_pattern = re.compile(r"<:[a-z]+:\d+>$")
        if answer and not emoji_pattern.search(answer.rstrip()):
            last_line = answer.rstrip().split("\n")[-1]
            if len(last_line) < 50:
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
