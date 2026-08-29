# =============================================
# features/chat.py
# Xử lý "nói chuyện" và "tóm tắt" — phần lõi gọi AI để trả lời tin nhắn.
# Tách từ bot.py. Nhận `bot` qua tham số, không import bot (tránh circular import).
# =============================================

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


# Prompt hệ thống dùng cho lệnh "tóm tắt" — yêu cầu AI tóm tắt khách quan, bỏ lời lăng mạ.
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


# Xử lý lệnh "tóm tắt" (vd: `chị cá tóm tắt 1 tiếng` / `tóm tắt 30 tin`).
# Lấy lịch sử kênh theo thời gian hoặc số tin, đưa cho AI tóm gọn.
# Trả về True sau khi xử lý xong (luôn tuân theo route trong bot.py).
async def handle_summary(message, bot) -> bool:
    raw = re.sub(r"^(chicha|chica)\s*", "", message.content, flags=re.I).strip()
    raw = re.sub(r"^(summary|t\u00f3m t\u1eaft)\s*", "", raw, flags=re.I).strip()

    now = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))
    after = None     # Mốc thời gian lấy từ đây trở đi (nếu tóm tắt theo khoảng giờ)
    limit = SUMMARY_LIMIT   # Mặc định lấy bao nhiêu tin

    # Phân tích "N phút/giờ/ngày" -> tóm tắt khoảng thời gian
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
        # Ngược lại: "N tin/tin nhắn" -> giới hạn số tin tối đa SUMMARY_MAX
        m_count = re.search(r"(\d+)\s*(tin|tin nhắn|messages?)?", raw, re.I)
        if m_count:
            limit = min(int(m_count.group(1)), SUMMARY_MAX)

    try:
        # Lấy lịch sử kênh: theo khoảng thời gian hoặc theo số tin (trước tin hiện tại)
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
        # Thiếu quyền Read Message History thường là nguyên nhân
        print(f"LỖI SUMMARY FETCH: {type(e).__name__}: {e}", flush=True)
        await message.channel.send(
            "Chị không lấy được lịch sử kênh 😭 (bot cần quyền **Read Message History**).",
            reference=message, mention_author=False,
        )
        return True

    # Trường hợp không lấy được có before (kênh ngắn) -> thử lấy lại giới hạn limit
    if not msgs and after is None:
        msgs = [m async for m in message.channel.history(limit=limit)]
        msgs = [m for m in msgs if m.id != message.id]   # Bỏ tin đang gửi lệnh

    msgs.reverse()   # Sắp xếp lại đúng thứ tự thời gian
    # Ghép thành văn bản "Tên: nội dung" để đưa vào AI
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
        # Gọi AI tóm tắt (chạy nền bằng to_thread để không chặn bot)
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
        if len(summary) > 2000:   # Giới hạn độ dài tin Discord
            summary = summary[:1997] + "..."
        await message.channel.send(summary, reference=message, mention_author=False)
    except Exception as e:
        print(f"LỖI SUMMARY: {type(e).__name__}: {e}", flush=True)
        await message.channel.send(
            "Chị tóm tắt hơi trục trặc rồi 😭", reference=message, mention_author=False
        )
    return True


# Xử lý phần lõi "nói chuyện": xác định đối tượng (bot/role), phát hiện chửi/chọc,
# tìm web, gọi AI sinh câu trả lời rồi gửi về kênh.
# Trả về True nếu đã xử lý xong tin này, False nếu không phải lúc cần trả lời.
async def handle_chat(message, bot) -> bool:
    bot_mentioned = bot.user in message.mentions          # Có tag bot không?
    role_mentioned = any(role.id == ROLE_ID for role in message.role_mentions)   # Tag đúng role?
    content_lower = message.content.lower()

    # Nếu không tag bot và cũng không có từ khóa gọi -> thử tính năng "chủ động nói"
    if not bot_mentioned and not role_mentioned:
        if not any(kw in content_lower for kw in KEYWORDS):
            # Xác suất ngẫu nhiên + độ dài tin + từ khóa để bot tự xen vào
            is_proactive = (
                len(message.content) > MIN_MESSAGE_LENGTH
                and random.random() < PROACTIVE_CHANCE
                and any(kw in content_lower for kw in PROACTIVE_KEYWORDS)
            )
            if not is_proactive:
                return False   # Không gọi bot -> bỏ qua hẳn
            # Đánh dấu đây là tin tự động để AI hiểu ngữ cảnh
            prompt = f"[TỰ ĐỘNG] {message.content}"
            sender_name = message.author.display_name or message.author.name

    # Phát hiện đây có phải là lời chửi hay bị chọc ghẹo không
    is_chui = (
        bot_mentioned
        or role_mentioned
        or any(kw in content_lower for kw in KEYWORDS)
    ) and any(kw in content_lower for kw in CHUI_KEYWORDS)
    is_provoked = any(kw in content_lower for kw in PROVOCATION_KEYWORDS)

    prompt = message.content

    # Gỡ mention bot/role ra khỏi chuỗi để chỉ gửi nội dung thật cho AI
    if bot.user:
        prompt = prompt.replace(bot.user.mention, "")
        prompt = prompt.replace(f"<@{bot.user.id}>", "")
        prompt = prompt.replace(f"<@!{bot.user.id}>", "")

    for role in message.role_mentions:
        prompt = prompt.replace(role.mention, "")

    prompt = prompt.strip()

    # Bỏ tiền tố lệnh `chica search` để chỉ gửi nội dung tìm kiếm thật cho AI
    prompt = re.sub(r"(?i)^\s*(chica)\s*search\s*", "", prompt).strip()

    sender_name = message.author.display_name or message.author.name

    # Thêm thẻ biểu thị cho AI biết kiểu tương tác
    if is_chui:
        prompt = f"[CHỬI] {prompt}"
    elif is_provoked:
        prompt = f"[CHỌC GHẸO] {prompt}"

    # Nếu user hỏi "ai đang online" -> trả về danh sách thành viên, không gọi AI
    is_member_list = any(kw in content_lower for kw in MEMBER_KEYWORDS)
    if is_member_list and message.guild:
        await handle_member_list(message, bot)
        return True

    # Phát hiện nhu cầu tìm kiếm web (vd: "tìm", "là ai", "khi nào"...)
    is_search = any(kw in content_lower for kw in SEARCH_KEYWORDS)

    # Nếu là câu hỏi tìm web (không phải chửi/chọc) -> tìm trên mạng rồi nạp vào prompt
    if is_search and not is_chui and not is_provoked:
        print(f"TÌM KIỂM: {prompt}", flush=True)
        search_results = await asyncio.to_thread(search_web, prompt)
        prompt = f"Thông tin tìm được trên mạng:\n{search_results}\n\nCâu hỏi của user: {prompt}"
        print(f"KẾT QUẢ TÌM KIỂM: {search_results[:200]}...", flush=True)

    # Không còn nội dung gì để gửi AI
    if not prompt:
        await message.channel.send(
            "M gọi Chị Cá đó hả? 🐟", reference=message, mention_author=False
        )
        return True

    channel_id = message.channel.id

    # Ghi nhớ user + lưu tin user vào lịch sử để bot có ngữ cảnh
    remember_user(message.author.id, sender_name)
    add_message(channel_id, "user", f"[{sender_name}]: {prompt}")

    try:
        print(f"GỬI AI: {prompt}", flush=True)

        # Prompt hệ thống cá nhân hóa theo người gọi + danh sách người đã biết
        system_prompt = get_system_prompt(sender_name, get_known_users())

        # Gọi AI (chạy nền bằng to_thread để không chặn bot)
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
                + get_history(channel_id),   # Nối vào lịch sử hội thoại kênh
            )

        ai_message = response.choices[0].message
        finish_reason = response.choices[0].finish_reason
        print("USAGE:", response.usage, flush=True)

        print("AI RAW CONTENT:", repr(ai_message.content), flush=True)
        print("FINISH REASON:", finish_reason, flush=True)

        # Dòng suy luận (reasoning) nếu model có xuất — chỉ để log
        reasoning_content = getattr(ai_message, "reasoning_content", None)
        if reasoning_content:
            print("AI REASONING:", repr(reasoning_content), flush=True)

        answer = ai_message.content or ""
        answer = clean_ai_response(answer)   # Dọn ký tự thừa / không hợp lệ

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

        if len(answer) > 2000:   # Giới hạn độ dài tin Discord
            answer = answer[:1997] + "..."

        # AI trả về tin rỗng -> báo phù hợp theo lý do kết thúc
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

        # Lưu câu trả lời vào lịch sử để các lần sau có ngữ cảnh
        add_message(channel_id, "assistant", answer)

    except Exception as e:
        print(f"LỖI AI: {type(e).__name__}: {e}", flush=True)
        await message.channel.send("Chị Cá bị lỗi khi gọi AI rồi 😭", reference=message, mention_author=False)

    return True
