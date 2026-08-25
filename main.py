import os

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
                        "Nói chuyện tự nhiên, thân thiện, "
                        "hơi hài hước và bằng tiếng Việt. "
                        "Không cần nói quá dài. "
                        f"Em đang nói chuyện với {sender_name}. "
                        "Nhớ context cuộc trò chuyện trước đó."
                    ),
                },
            ] + chat_history[channel_id],
        )

        answer = response.choices[0].message.content or ""

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

