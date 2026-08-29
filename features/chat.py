import asyncio
import random
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import discord

from config import (
    KEYWORDS,
    CHUI_KEYWORDS,
    PROVOCATION_KEYWORDS,
    SEARCH_KEYWORDS,
    PROACTIVE_CHANCE,
    MIN_MESSAGE_LENGTH,
    PROACTIVE_KEYWORDS,
    MODEL_NAME,
    MEMBER_KEYWORDS,
    EMOJI_MAP,
    SUMMARY_KEYWORDS,
    SUMMARY_LIMIT,
    SUMMARY_MAX,
    ROLE_ID,
)
from ai import ai, get_system_prompt, clean_ai_response
from memory import add_message, get_history, remember_user, get_known_users
from search import search_web
from features.server_tools import handle_member_list


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


async def handle_summary(message, bot) -> bool:
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
            reference=message, mention_author=False,
        )
        return True

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
            reference=message, mention_author=False,
        )
        return True

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
        await message.channel.send(summary, reference=message, mention_author=False)
    except Exception as e:
        print(f"LỖI SUMMARY: {type(e).__name__}: {e}", flush=True)
        await message.channel.send(
            "Chị tóm tắt hơi trục trặc rồi 😭", reference=message, mention_author=False
        )
    return True


async def handle_chat(message, bot) -> bool:
    bot_mentioned = bot.user in message.mentions
    role_mentioned = any(role.id == ROLE_ID for role in message.role_mentions)
    content_lower = message.content.lower()

    if not bot_mentioned and not role_mentioned:
        if not any(kw in content_lower for kw in KEYWORDS):
            is_proactive = (
                len(message.content) > MIN_MESSAGE_LENGTH
                and random.random() < PROACTIVE_CHANCE
                and any(kw in content_lower for kw in PROACTIVE_KEYWORDS)
            )
            if not is_proactive:
                return False
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
        await handle_member_list(message, bot)
        return True

    is_search = any(kw in content_lower for kw in SEARCH_KEYWORDS)

    if is_search and not is_chui and not is_provoked:
        print(f"TÌM KIỂM: {prompt}", flush=True)
        search_results = await asyncio.to_thread(search_web, prompt)
        prompt = f"Thông tin tìm được trên mạng:\n{search_results}\n\nCâu hỏi của user: {prompt}"
        print(f"KẾT QUẢ TÌM KIỂM: {search_results[:200]}...", flush=True)

    if not prompt:
        await message.channel.send(
            "M gọi Chị Cá đó hả? 🐟", reference=message, mention_author=False
        )
        return True

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

        for placeholder, emoji in EMOJI_MAP.items():
            answer = answer.replace(placeholder, emoji)

        answer = re.sub(r"\[:([a-z]+:\d+)\]", r"<:\1>", answer)
        answer = re.sub(r"(?<!<):([a-z]+):(\d+):", r"<:\1:\2>", answer)

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
                    reference=message, mention_author=False,
                )
            else:
                await message.channel.send(
                    "Chị Cá không biết trả lời sao 😅", reference=message, mention_author=False
                )
            return True

        print(f"AI: {answer}", flush=True)

        await message.channel.send(answer, reference=message, mention_author=False)

        add_message(channel_id, "assistant", answer)

    except Exception as e:
        print(f"LỖI AI: {type(e).__name__}: {e}", flush=True)
        await message.channel.send("Chị Cá bị lỗi khi gọi AI rồi 😭", reference=message, mention_author=False)

    return True
