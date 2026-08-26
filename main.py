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

MODEL_NAME = "qwen/qwen3.8-27b"

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
# XỬ LÝ THINKING (lớp phòng thủ dự phòng)
# =========================
#
# Với reasoning_effort="none", Qwen3.6 sẽ không sinh phần <think> nữa.
# Hàm này vẫn được giữ lại làm lớp bảo vệ thứ 2, phòng trường hợp model
# lách quy tắc hoặc trả về định dạng khác, kèm regex mở rộng để bắt
# nhiều biến thể tag hơn.

def clean_ai_response(answer: str) -> str:
    """
    Xóa các dạng thinking/reasoning mà model có thể trả về.
    """

    if not answer:
        return ""

    # ---------------------------------
    # <think>/<thinking>/<reasoning>/<analysis> ... đóng đúng cặp
    # (cho phép thuộc tính trong tag, khoảng trắng linh hoạt)
    # ---------------------------------

    answer = re.sub(
        r"<\s*think(?:ing)?[^>]*>.*?<\s*/\s*think(?:ing)?\s*>",
        "",
        answer,
        flags=re.DOTALL | re.IGNORECASE
    )

    answer = re.sub(
        r"<\s*reasoning[^>]*>.*?<\s*/\s*reasoning\s*>",
        "",
        answer,
        flags=re.DOTALL | re.IGNORECASE
    )

    answer = re.sub(
        r"<\s*analysis[^>]*>.*?<\s*/\s*analysis\s*>",
        "",
        answer,
        flags=re.DOTALL | re.IGNORECASE
    )

    # ---------------------------------
    # Trường hợp tag mở nhưng KHÔNG đóng
    # (model bị cắt cụt giữa lúc đang "nghĩ")
    # ---------------------------------

    unclosed_match = re.search(
        r"<\s*(think(?:ing)?|reasoning|analysis)[^>]*>",
        answer,
        flags=re.IGNORECASE
    )

    if unclosed_match:
        answer = answer[:unclosed_match.start()]

    # ---------------------------------
    # Một số model dùng:
    #
    # Thinking:
    # ...
    #
    # Answer:
    # ...
    # ---------------------------------

    answer = re.sub(
        r"^\s*(thinking|reasoning|chain\s+of\s+thought)\s*:.*?"
        r"(?:answer|final)\s*:\s*",
        "",
        answer,
        flags=re.DOTALL | re.IGNORECASE
    )

    # ---------------------------------
    # Nếu còn "Answer:" ở đầu
    # ---------------------------------

    answer = re.sub(
        r"^\s*(answer|final)\s*:\s*",
        "",
        answer,
        flags=re.IGNORECASE
    )

    # ---------------------------------
    # Dọn khoảng trắng
    # ---------------------------------

    answer = answer.strip()

    return answer


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
        "chửi",
    ]

    if not bot_mentioned and not role_mentioned:

        if not any(
            kw in content_lower
            for kw in keywords
        ):
            return

    # =========================
    # DETECT CHỬI / CHỌC GHẸO
    # =========================

    is_chui = any(
        kw in content_lower
        for kw in ["chửi"]
    )

    provocation_keywords = [
        "ngu", "đần", "câm", "đồ ngu", "mày ngu",
        "bạn ngu", "dở", "kém", "tệ", "loser",
        "đồ khùng", "đồ điên", "bẩn", "xấu",
    ]

    is_provoked = any(
        kw in content_lower
        for kw in provocation_keywords
    )

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
    # THÊM TAG CHỬI
    # =========================

    if is_chui:
        prompt = f"[CHỬI] {prompt}"
    elif is_provoked:
        prompt = f"[CHỌC GHẸO] {prompt}"

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
            "Bạn là Chị Cá 🐟, "
            "một AI đang sống trong Discord. "

            "Xưng chị, gọi người khác là em. "

            "Lạnh lùng, điềm tĩnh, nói ít nhưng chất. "

            "Không quá đanh đá hay cay độc, "
            "thiên hướng nhẹ nhàng, ấm áp phía sau vẻ ngoài lạnh. "

            "Thỉnh thoảng châm biếm nhẹ, không cay người. "

            "Không nịnh bợ. "
            "Câu trả lời phải NGẮN GỌN, tối đa 2-3 câu. Không dài dòng. "

            f"Em đang nói chuyện với {sender_name}. "

            "Nhớ context cuộc trò chuyện trước đó. "

            "CHỬI TỤC: "
            "Khi có tag [CHỬI] hoặc [CHỌC GHẸO], chửi tục NẶNG. "
            "Dùng từ ngữ thô tục, gay gắt, cay độc, không cần giữ ý. "
            "Khi được yêu cầu chửi ai → chửi thẳng vào người đó, nặng nề. "
            "Khi bị xúc phạm → chửi lại thậm tệ hơn. "
            "Sau khi chửi xong, quay lại bình thường. "

            "Sử dụng emoji Discord theo ngữ cảnh: "

            "<:skirkmeow:1471088875106730106> khi dễ thương, "

            "<:skirkheart:1471089365500559455> khi yêu thương, "

            "<:skirksmile:1471089210881478768> khi vui, "

            "<:skirkangry:1471089056975687814> khi giận. "

            "Chỉ dùng emoji khi thực sự phù hợp, không spam. "
            "Tuyệt đối KHÔNG dùng LaTeX ($...$, \\frac, \\text, v.v.). "
            "Viết công thức toán bằng text thuần: dùng ký tự Unicode như ≈, ², ³, √, π, Δ, ÷, ×, ≥, ≤. "
            "Ví dụ: a ≈ 5.05 m/s², T ≈ 9.69 N. "
            "Trả lời HOÀN TOÀN bằng tiếng Việt. Tuyệt đối không dùng ký tự tiếng Trung hay bất kỳ ngôn ngữ nào khác. "
            "Nếu muốn nói từ tiếng Trung hay tiếng Anh, PHẢI dịch sang tiếng Việt trước khi trả lời."
        )

        # =========================
        # GỌI GROQ
        # =========================
        #
        # reasoning_effort="default" -> bật chế độ thinking của Qwen3.8
        #                            (tham số CHÍNH THỨC được SDK hỗ trợ,
        #                            không cần reasoning_format nữa)
        # max_tokens tăng lên      -> tránh bị cắt cụt giữa chừng

        response = await asyncio.to_thread(
            ai.chat.completions.create,
            model=MODEL_NAME,
            reasoning_effort="default",
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
        finish_reason = response.choices[0].finish_reason
        print("USAGE:", response.usage, flush=True)
        # =========================
        # DEBUG RAW
        # =========================

        print(
            "AI RAW CONTENT:",
            repr(ai_message.content),
            flush=True
        )

        print(
            "FINISH REASON:",
            finish_reason,
            flush=True
        )

        # Nếu SDK/model có reasoning_content
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
        # LẤY CONTENT
        # =========================

        answer = ai_message.content or ""

        # =========================
        # XÓA THINKING (lớp phòng thủ dự phòng)
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
        # XÓA TAG CHỬI / CHỌC GHẸO
        # =========================

        answer = re.sub(r"\[CHỬI\]\s*", "", answer)
        answer = re.sub(r"\[CHỌC GHẸO\]\s*", "", answer)

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

            if finish_reason == "length":

                await message.channel.send(
                    "Câu này hơi dài, chị bị cắt ngang lúc đang trả lời rồi 😅 "
                    "em hỏi ngắn gọn lại giúp chị nhé."
                )

            else:

                await message.channel.send(
                    "Chị Cá không biết trả lời sao 😅"
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