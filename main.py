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

    print(f"Web server đã start tại port {port}", flush=True)


# =========================
# XỬ LÝ THINKING (FIX LỖI THẺ MỞ KHÔNG ĐÓNG)
# =========================

def clean_ai_response(answer: str) -> str:
    """
    Xóa triệt để các dạng thinking/reasoning dù có hay không có thẻ đóng </think>.
    """
    if not answer:
        return ""

    tags = ["think", "reasoning", "analysis", "thought"]

    # 1. Nếu có đủ cặp thẻ <think>...</think> -> Xóa khối ở giữa
    for tag in tags:
        answer = re.sub(rf"<{tag}>[\s\S]*?</{tag}>", "", answer, flags=re.IGNORECASE)

    # 2. Xử lý trường hợp thẻ <think> mở nhưng KHÔNG CÓ thẻ đóng </think>
    for tag in tags:
        if f"<{tag}>" in answer.lower():
            parts = re.split(rf"<{tag}>", answer, flags=re.IGNORECASE)
            clean_text = parts[0]
            
            for part in parts[1:]:
                if f"</{tag}>" in part.lower():
                    clean_text += re.split(rf"</{tag}>", part, flags=re.IGNORECASE)[-1]
                else:
                    # Trường hợp trôi thẻ đóng hoàn toàn: Tách theo dòng và lọc dòng nháp của AI
                    lines = part.split("\n")
                    non_thinking_lines = []
                    is_thinking = True
                    
                    for line in lines:
                        # Dấu hiệu bắt đầu câu trả lời thực sự (Tiếng Việt hoặc đầu mục)
                        strip_line = line.strip()
                        if any(marker in strip_line for marker in ["a)", "b)", "c)", "d)", "1.", "2.", "Gia tốc", "Đáp án", "Chị", "Em"]) and not strip_line.startswith("*"):
                            is_thinking = False
                        
                        if not is_thinking:
                            non_thinking_lines.append(line)
                            
                    clean_text += "\n".join(non_thinking_lines)
            answer = clean_text

    # 3. Loại bỏ khối markdown code block chứa thinking (VD: ```thinking ... ```)
    answer = re.sub(r"```(?:thinking|thought|reasoning)[\s\S]*?```", "", answer, flags=re.IGNORECASE)

    # 4. Loại bỏ dạng văn bản: "Thinking:\n...\nAnswer:\n..."
    answer = re.sub(
        r"^\s*(?:thinking|reasoning|chain\s+of\s+thought)\s*:[\s\S]*?(?:answer|final answer)\s*:\s*",
        "",
        answer,
        flags=re.IGNORECASE
    )
    answer = re.sub(r"^\s*(?:answer|final answer)\s*:\s*", "", answer, flags=re.IGNORECASE)

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

    # Xóa mention bot
    if bot.user:

        prompt = prompt.replace(
            bot.user.mention,
            ""
        )

        # Xóa <@ID>
        prompt = prompt.replace(
            f"<@{bot.user.id}>",
            ""
        )

        # Xóa <@!ID>
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
    # GIỮ HISTORY TRONG GIỚI HẠN
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
            "Bạn là Chị Cá 🐟, một AI đang sống trong Discord. "
            "Xưng chị, gọi người khác là em. "
            "Lạnh lùng, điềm tĩnh, nói ít nhưng chất. "
            "Không quá đanh đá hay cay độc, thiên hướng nhẹ nhàng, ấm áp phía sau vẻ ngoài lạnh. "
            "Thỉnh thoảng châm biếm nhẹ, không cay người. Không nịnh bợ. Không cần nói quá dài. "
            f"Em đang nói chuyện với {sender_name}. "
            "Nhớ context cuộc trò chuyện trước đó. "
            "Sử dụng emoji Discord theo ngữ cảnh: "
            "<:skirkmeow:1471088875106730106> khi dễ thương, "
            "<:skirkheart:1471089365500559455> khi yêu thương, "
            "<:skirksmile:1471089210881478768> khi vui, "
            "<:skirkangry:1471089056975687814> khi giận. "
            "Chỉ dùng emoji khi thực sự phù hợp, không spam. "
            "Trả lời trực tiếp bằng tiếng Việt, tuyệt đối không xuất các bước suy luận tiếng Anh."
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

        reasoning_content = getattr(
            ai_message,
            "reasoning_content",
            None
        )

        if reasoning_content:

            print(
                "AI REASONING:",
                repr(reasoning_content),
                flush=True
            )

        # =========================
        # LẤY CONTENT & CLEAN
        # =========================

        answer = ai_message.content or ""
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
        # GIỚI HẠN DISCORD 2000 KÝ TỰ
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

            await message.channel.send(
                "Chị Cá không biết trả lời sao 😅"
            )

            return

        # =========================
        # LOG & GỬI DISCORD
        # =========================

        print(
            f"AI: {answer}",
            flush=True
        )

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