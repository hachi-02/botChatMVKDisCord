import os
import re
import asyncio

import discord
from dotenv import load_dotenv
from openai import OpenAI
from aiohttp import web

load_dotenv()

# =========================
# CONFIG
# =========================

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# ID role dùng để kích hoạt bot
ROLE_ID = 1541912537744936983

# =========================
# GROQ AI
# =========================

ai = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1",
)

# =========================
# DISCORD
# =========================

intents = discord.Intents.default()
intents.message_content = True

bot = discord.Client(intents=intents)

# =========================
# MEMORY
# =========================

chat_history = {}  # {channel_id: [{"role": ..., "content": ...}]}

MAX_HISTORY = 20

# =========================
# WEB SERVER
# =========================

web_runner = None


async def health(request):
    return web.Response(text="OK")


async def start_web_server():
    global web_runner

    # Tránh start server nhiều lần khi Discord reconnect
    if web_runner is not None:
        return

    app = web.Application()
    app.router.add_get("/", health)

    web_runner = web.AppRunner(app)
    await web_runner.setup()

    port = int(os.getenv("PORT", 8080))

    site = web.TCPSite(
        web_runner,
        "0.0.0.0",
        port
    )

    await site.start()

    print(
        f"Web server đã start tại port {port}",
        flush=True
    )


# =========================
# XỬ LÝ THINKING
# =========================

def clean_ai_response(answer: str) -> str:
    """
    Loại bỏ thinking/reasoning nếu model vẫn vô tình trả ra.
    """

    if not answer:
        return ""

    # =================================
    # <think>...</think>
    # =================================

    match = re.search(
        r"<think>.*?</think>\s*(.*)",
        answer,
        flags=re.DOTALL | re.IGNORECASE
    )

    if match:
        answer = match.group(1)

    else:
        # <think> không đóng
        match = re.search(
            r"<think>",
            answer,
            flags=re.IGNORECASE
        )

        if match:
            # Không có final answer rõ ràng.
            # Tuyệt đối không gửi thinking.
            return ""

    # =================================
    # <reasoning>...</reasoning>
    # =================================

    match = re.search(
        r"<reasoning>.*?</reasoning>\s*(.*)",
        answer,
        flags=re.DOTALL | re.IGNORECASE
    )

    if match:
        answer = match.group(1)

    else:
        match = re.search(
            r"<reasoning>",
            answer,
            flags=re.IGNORECASE
        )

        if match:
            return ""

    # =================================
    # <analysis>...</analysis>
    # =================================

    match = re.search(
        r"<analysis>.*?</analysis>\s*(.*)",
        answer,
        flags=re.DOTALL | re.IGNORECASE
    )

    if match:
        answer = match.group(1)

    else:
        match = re.search(
            r"<analysis>",
            answer,
            flags=re.IGNORECASE
        )

        if match:
            return ""

    # =================================
    # Thinking: ... Answer:
    # =================================

    answer = re.sub(
        r"^\s*(thinking|reasoning|chain\s+of\s+thought)\s*:.*?"
        r"(?:answer|final)\s*:\s*",
        "",
        answer,
        flags=re.DOTALL | re.IGNORECASE
    )

    # =================================
    # Answer: / Final:
    # =================================

    answer = re.sub(
        r"^\s*(answer|final)\s*:\s*",
        "",
        answer,
        flags=re.IGNORECASE
    )

    return answer.strip()


# =========================
# BOT ONLINE
# =========================

@bot.event
async def on_ready():

    print(
        f"Bot đã online: {bot.user}",
        flush=True
    )

    await start_web_server()

    print(
        "Chị Cá đã sẵn sàng 🐟",
        flush=True
    )


# =========================
# NHẬN MESSAGE
# =========================

@bot.event
async def on_message(message):

    # =========================
    # DEBUG
    # =========================

    print(
        f"NHẬN MESSAGE: "
        f"{message.author}: "
        f"{message.content}",
        flush=True
    )

    # =========================
    # KHÔNG TRẢ LỜI CHÍNH MÌNH
    # =========================

    if message.author == bot.user:
        return

    # =========================
    # KHÔNG TRẢ LỜI DM
    # =========================

    if message.guild is None:
        return

    # =========================
    # KIỂM TRA MENTION BOT
    # =========================

    bot_mentioned = bot.user in message.mentions

    # =========================
    # KIỂM TRA MENTION ROLE
    # =========================

    role_mentioned = any(
        role.id == ROLE_ID
        for role in message.role_mentions
    )

    # =========================
    # KEYWORD
    # =========================

    if not bot_mentioned and not role_mentioned:

        content_lower = message.content.lower()

        keywords = [
            "chị cá",
            "chica",
            "chicá",
            "chị ca",
            "cá ơi",
            "ca ơi",
            "ê chị cá",
            "ê chica",
            "chị cá ơi",
            "chica ơi",
        ]

        if not any(
            kw in content_lower
            for kw in keywords
        ):
            return

    # =========================
    # LẤY NỘI DUNG
    # =========================

    prompt = message.content

    # =========================
    # XÓA MENTION BOT
    # =========================

    if bot.user:

        prompt = prompt.replace(
            bot.user.mention,
            ""
        )

        prompt = prompt.replace(
            f"<@{bot.user.id}>",
            ""
        )

        prompt = prompt.replace(
            f"<@!{bot.user.id}>",
            ""
        )

    # =========================
    # XÓA MENTION ROLE
    # =========================

    for role in message.role_mentions:

        prompt = prompt.replace(
            role.mention,
            ""
        )

    prompt = prompt.strip()

    # =========================
    # TÊN THÀNH VIÊN
    # =========================

    sender_name = (
        message.author.display_name
        or message.author.name
    )

    # =========================
    # CHỈ MENTION KHÔNG TEXT
    # =========================

    if not prompt:

        await message.channel.send(
            "M gọi Chị Cá đó hả? 🐟"
        )

        return

    # =========================
    # LỊCH SỬ CHAT
    # =========================

    channel_id = message.channel.id

    if channel_id not in chat_history:
        chat_history[channel_id] = []

    # =========================
    # THÊM USER MESSAGE
    # =========================

    chat_history[channel_id].append(
        {
            "role": "user",
            "content": f"[{sender_name}]: {prompt}"
        }
    )

    # =========================
    # GIỮ HISTORY
    # =========================

    if len(chat_history[channel_id]) > MAX_HISTORY:

        chat_history[channel_id] = (
            chat_history[channel_id][-MAX_HISTORY:]
        )

    # =========================
    # GỌI AI
    # =========================

    try:

        print(
            f"GỬI AI: {prompt}",
            flush=True
        )

        # =========================
        # SYSTEM PROMPT
        # =========================

        system_prompt = (
            "Bạn là Chị Cá 🐟, "
            "một AI đang sống trong Discord. "

            "Xưng chị, gọi người khác là em. "

            "Lạnh lùng, điềm tĩnh, nói ít nhưng chất. "

            "Không quá đanh đá hay cay độc, "
            "thiên hướng nhẹ nhàng, ấm áp phía sau vẻ ngoài lạnh. "

            "Thỉnh thoảng châm biếm nhẹ, không cay người. "

            "Không nịnh bợ. "
            "Không cần nói quá dài. "

            f"Em đang nói chuyện với {sender_name}. "

            "Nhớ context cuộc trò chuyện trước đó. "

            "Sử dụng emoji Discord theo ngữ cảnh: "

            "<:skirkmeow:1471088875106730106> khi dễ thương, "
            "<:skirkheart:1471089365500559455> khi yêu thương, "
            "<:skirksmile:1471089210881478768> khi vui, "
            "<:skirkangry:1471089056975687814> khi giận. "

            "Chỉ dùng emoji khi thực sự phù hợp, không spam. "

            "Không hiển thị reasoning, thinking, "
            "phân tích nội bộ hoặc chain-of-thought. "

            "Chỉ trả về câu trả lời cuối cùng."
        )

        # =========================
        # GỌI GROQ
        # =========================

        response = await asyncio.to_thread(
            ai.chat.completions.create,

            model="qwen/qwen3.6-27b",

            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
                }
            ] + chat_history[channel_id],

            # =========================
            # TẮT THINKING
            # =========================

            reasoning_effort="none",

            # Thiết lập phù hợp non-thinking
            temperature=0.7,
            top_p=0.80,

            max_completion_tokens=2048,
        )

        # =========================
        # LẤY MESSAGE
        # =========================

        ai_message = response.choices[0].message

        # =========================
        # DEBUG RAW
        # =========================

        print(
            "AI RAW CONTENT:",
            repr(ai_message.content),
            flush=True
        )

        # =========================
        # DEBUG REASONING
        # =========================

        reasoning_content = getattr(
            ai_message,
            "reasoning_content",
            None
        )

        if reasoning_content:

            print(
                "AI REASONING ĐÃ BỊ ẨN:",
                "[hidden]",
                flush=True
            )

        # =========================
        # LẤY CONTENT
        # =========================

        answer = ai_message.content or ""

        # =========================
        # XÓA THINKING DỰ PHÒNG
        # =========================

        answer = clean_ai_response(answer)

        # =========================
        # DEBUG SAU KHI CLEAN
        # =========================

        print(
            "AI CLEAN:",
            repr(answer),
            flush=True
        )

        # =========================
        # GIỚI HẠN DISCORD
        # =========================

        if len(answer) > 2000:

            answer = (
                answer[:1997]
                + "..."
            )

        # =========================
        # KHÔNG CÓ ANSWER
        # =========================

        if not answer.strip():

            print(
                "AI KHÔNG CÓ FINAL ANSWER",
                flush=True
            )

            # Xóa user message vừa thêm
            # để thinking/rỗng không ảnh hưởng memory
            if chat_history[channel_id]:
                chat_history[channel_id].pop()

            await message.channel.send(
                "Chị Cá bị khựng một chút 😅"
            )

            return

        # =========================
        # LOG
        # =========================

        print(
            f"AI: {answer}",
            flush=True
        )

        # =========================
        # GỬI DISCORD
        # =========================

        await message.channel.send(
            answer
        )

        # =========================
        # LƯU AI RESPONSE
        # =========================

        chat_history[channel_id].append(
            {
                "role": "assistant",
                "content": answer
            }
        )

        # =========================
        # GIỮ HISTORY
        # =========================

        if len(chat_history[channel_id]) > MAX_HISTORY:

            chat_history[channel_id] = (
                chat_history[channel_id][-MAX_HISTORY:]
            )

    # =========================
    # LỖI
    # =========================

    except Exception as e:

        print(
            f"LỖI AI: {type(e).__name__}: {e}",
            flush=True
        )

        await message.channel.send(
            "Chị Cá bị lỗi khi gọi AI rồi 😭"
        )


# =========================
# START BOT
# =========================

if not DISCORD_TOKEN:

    raise RuntimeError(
        "Không tìm thấy DISCORD_TOKEN trong .env"
    )

if not GROQ_API_KEY:

    raise RuntimeError(
        "Không tìm thấy GROQ_API_KEY trong .env"
    )

print(
    "Đang khởi động Chị Cá...",
    flush=True
)

bot.run(DISCORD_TOKEN)