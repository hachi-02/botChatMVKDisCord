import os
import re
import httpx2

import discord
from dotenv import load_dotenv
from openai import OpenAI
from aiohttp import web
from duckduckgo_search import DDGS

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

chat_history = {}  # {channel_id: [{"role":..., "content":...}]}
MAX_HISTORY = 20

# =========================
# WEB SERVER (giữ Render không sleep)
# =========================

async def health(request):
    return web.Response(text="OK")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 8080)))
    await site.start()


# =========================
# BOT ONLINE
# =========================

@bot.event
async def on_ready():
    print(f"Bot đã online: {bot.user}", flush=True)
    await start_web_server()
    print("Web server đã start", flush=True)


# =========================
# NHẬN MESSAGE
# =========================

@bot.event
async def on_message(message):

    # Debug
    print(
        f"NHẬN MESSAGE: "
        f"{message.author}: "
        f"{message.content}",
        flush=True
    )

    # Không trả lời chính mình
    if message.author == bot.user:
        return

    # Không trả lời tin nhắn riêng (DM)
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

    # Không mention bot hoặc role → bỏ qua
    if not bot_mentioned and not role_mentioned:
        # Kiểm tra keyword tên bot
        content_lower = message.content.lower()
        keywords = [
            "chị cá", "chica", "chicá",
            "chị ca", "chica",
            "cá ơi", "ca ơi",
            "ê chị cá", "ê chica",
            "chị cá ơi", "chica ơi",
        ]
        if not any(kw in content_lower for kw in keywords):
            return

    # =========================
    # LẤY NỘI DUNG
    # =========================

    prompt = message.content

    # Xóa mention bot
    prompt = prompt.replace(
        bot.user.mention,
        ""
    )

    # Xóa mention dạng <@ID>
    prompt = prompt.replace(
        f"<@{bot.user.id}>",
        ""
    )

    # Xóa mention dạng <@!ID>
    prompt = prompt.replace(
        f"<@!{bot.user.id}>",
        ""
    )

    # Xóa mention role
    for role in message.role_mentions:
        prompt = prompt.replace(
            role.mention,
            ""
        )

    prompt = prompt.strip()

    # =========================
    # TÊN THÀNH VIÊN
    # =========================

    sender_name = message.author.display_name or message.author.name

    # =========================
    # LỊCH SỬ CHAT
    # =========================

    channel_id = message.channel.id
    if channel_id not in chat_history:
        chat_history[channel_id] = []

    # Thêm tin nhắn user vào lịch sử
    chat_history[channel_id].append({
        "role": "user",
        "content": f"[{sender_name}]: {prompt}"
    })

    # Giữ lịch sử trong giới hạn
    if len(chat_history[channel_id]) > MAX_HISTORY:
        chat_history[channel_id] = chat_history[channel_id][-MAX_HISTORY:]

    # =========================
    # CHỈ MENTION KHÔNG CÓ TEXT
    # =========================

    if not prompt:
        await message.channel.send(
            "M gọi Chị Cá đó hả? 🐟"
        )
        return

    # =========================
    # LỆNH ĐẶC BIỆT
    # =========================

    prompt_lower = prompt.lower().strip()

    # --- PING ---
    if prompt_lower in ["ping", "chị cá ping", "chica ping"]:
        latency = round(bot.latency * 1000)
        await message.channel.send(f"Pong! {latency}ms")
        return

    # --- TÌM KIẾM ---
    if prompt_lower.startswith("tìm ") or prompt_lower.startswith("search "):
        query = prompt.split(" ", 1)[1] if " " in prompt else ""
        if not query:
            await message.channel.send("Gõ gì đi chị mới tìm được.")
            return
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=3))
            if not results:
                await message.channel.send("Không tìm thấy gì cả.")
                return
            msg = f"**Kết quả tìm \"{query}\":**\n\n"
            for i, r in enumerate(results, 1):
                msg += f"**{i}. {r['title']}**\n{r['href']}\n{r['body'][:100]}...\n\n"
            await message.channel.send(msg[:2000])
        except Exception as e:
            print(f"LỖI SEARCH: {e}", flush=True)
            await message.channel.send("Lỗi tìm kiếm rồi.")
        return

    # --- THỜI TIẾT ---
    if prompt_lower.startswith("thời tiết ") or prompt_lower.startswith("weather "):
        location = prompt.split(" ", 1)[1] if " " in prompt else ""
        if not location:
            await message.channel.send("Nhập địa điểm đi.")
            return
        try:
            r = httpx2.get(f"https://wttr.in/{location}?format=3&lang=vi", timeout=10)
            await message.channel.send(r.text.strip())
        except Exception as e:
            print(f"LỖI WEATHER: {e}", flush=True)
            await message.channel.send("Lỗi lấy thời tiết rồi.")
        return

    # =========================
    # GỌI AI
    # =========================

    try:

        print(f"GỬI AI: {prompt}", flush=True)

        response = ai.chat.completions.create(
            model="qwen/qwen3.6-27b",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Bạn là Chị Cá 🐟, "
                        "một AI đang sống trong Discord. "
                        "Xưng chị, gọi người khác là em. "
                        "Lạnh lùng, điềm tĩnh, nói ít nhưng chất. "
                        "Không quá đanh đá hay cay độc, "
                        "thiên hướng nhẹ nhàng, ấm áp phía sau vẻ ngoài lạnh. "
                        "Thỉnh thoảng châm biếm nhẹ, không cay người. "
                        "Không nịnh bợ. Không cần nói quá dài. "
                        f"Em đang nói chuyện với {sender_name}. "
                        "Nhớ context cuộc trò chuyện trước đó. "
                        "Sử dụng emoji Discord theo ngữ cảnh: "
                        "<:skirkmeow:1471088875106730106> khi dễ thương, "
                        "<:skirkheart:1471089365500559455> khi yêu thương, "
                        "<:skirksmile:1471089210881478768> khi vui, "
                        "<:skirkangry:1471089056975687814> khi giận. "
                        "Chỉ dùng emoji khi thực sự phù hợp, không spam."
                    ),
                },
            ] + chat_history[channel_id],
        )

        answer = response.choices[0].message.content or ""

        # Xóa thinking tags và thinking leak
        answer = re.sub(r"<think>.*?</think>", "", answer, flags=re.DOTALL).strip()
        answer = re.sub(r"<reasoning>.*?</reasoning>", "", answer, flags=re.DOTALL).strip()
        # Xóa nếu bắt đầu bằng "Okay" hoặc "Let me" (thinking leak)
        lines = answer.split("\n")
        clean_lines = []
        skip = True
        for line in lines:
            if skip and any(line.strip().startswith(x) for x in ["Okay,", "Let me", "The user", "Here's", "I need", "Thinking", "Alright"]):
                continue
            skip = False
            clean_lines.append(line)
        answer = "\n".join(clean_lines).strip()

        # Nếu vẫn còn quá dài → cắt ngắn
        if len(answer) > 2000:
            answer = answer[:1997] + "..."

        print(f"AI: {answer}", flush=True)

        # =========================
        # GỬI TRẢ LỜI
        # =========================

        if not answer.strip():
            await message.channel.send(
                "Chị Cá không biết trả lời sao 😅"
            )
            return

        await message.channel.send(answer)

        # Lưu reply vào lịch sử
        chat_history[channel_id].append({
            "role": "assistant",
            "content": answer
        })

    except Exception as e:

        print(f"LỖI AI: {e}", flush=True)

        await message.channel.send(
            "Chị Cá bị lỗi khi gọi AI rồi 😭"
        )


# =========================
# START BOT
# =========================

bot.run(DISCORD_TOKEN)

