from config import DISCORD_TOKEN, GROQ_API_KEY
from bot import bot

if not DISCORD_TOKEN:
    raise RuntimeError("Không tìm thấy DISCORD_TOKEN trong .env")

if not GROQ_API_KEY:
    raise RuntimeError("Không tìm thấy GROQ_API_KEY trong .env")

print("Đang khởi động Chị Cá...", flush=True)

bot.run(DISCORD_TOKEN)
