import os
import re
import asyncio

import discord
from dotenv import load_dotenv
from openai import OpenAI
from aiohttp import web
import yt_dlp

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
# MUSIC QUEUE
# =========================

music_queues = {}  # {guild_id: [{"title": ..., "url": ..., "channel": ...}]}

# yt-dlp options
ydl_opts = {
    "format": "bestaudio/best",
    "quiet": True,
    "no_warnings": True,
    "extract_flat": False,
    "default_search": "ytsearch1",
    "extractor_args": {
        "youtube": {
            "player_client": ["ios", "web_creator"],
        }
    },
    "http_headers": {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    },
}

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
# XỬ LÝ THINKING
# =========================

async def play_next(guild_id):
    """Phát bài tiếp theo trong queue."""

    if guild_id not in music_queues or not music_queues[guild_id]:
        return

    song = music_queues[guild_id][0]
    channel = song["channel"]
    guild = channel.guild

    # Kết nối voice channel
    if not guild.voice_client:
        try:
            vc = await channel.connect()
        except Exception as e:
            print(f"LỖI CONNECT VOICE: {e}", flush=True)
            return
    else:
        vc = guild.voice_client

    # FFMPEG options
    ffmpeg_opts = {
        "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
        "options": "-vn",
    }

    try:
        source = discord.FFmpegPCMAudio(
            song["url"],
            **ffmpeg_opts,
        )

        def after_playing(error):
            if error:
                print(f"LỖI PLAY: {error}", flush=True)
            # Xóa bài đã phát
            if guild_id in music_queues and music_queues[guild_id]:
                music_queues[guild_id].pop(0)
            # Phát bài tiếp
            asyncio.run_coroutine_threadsafe(
                play_next(guild_id),
                bot.loop,
            )

        vc.play(
            source,
            after=after_playing,
        )

        await channel.send(f"🎶 Đang phát: **{song['title']}**")

    except Exception as e:
        print(f"LỖI PLAY: {e}", flush=True)
        await channel.send("Lỗi phát nhạc rồi.")
        if guild_id in music_queues and music_queues[guild_id]:
            music_queues[guild_id].pop(0)
        await play_next(guild_id)


def clean_ai_response(answer: str) -> str:
    """
    Xóa các dạng thinking/reasoning mà model có thể trả về.
    """

    if not answer:
        return ""

    # ---------------------------------
    # <think>...</think>
    # ---------------------------------

    answer = re.sub(
        r"<think>.*?</think>",
        "",
        answer,
        flags=re.DOTALL | re.IGNORECASE
    )

    # ---------------------------------
    # <reasoning>...</reasoning>
    # ---------------------------------

    answer = re.sub(
        r"<reasoning>.*?</reasoning>",
        "",
        answer,
        flags=re.DOTALL | re.IGNORECASE
    )

    # ---------------------------------
    # <analysis>...</analysis>
    # ---------------------------------

    answer = re.sub(
        r"<analysis>.*?</analysis>",
        "",
        answer,
        flags=re.DOTALL | re.IGNORECASE
    )

    # ---------------------------------
    # Trường hợp <think> không đóng
    # ---------------------------------

    think_match = re.search(
        r"<think>",
        answer,
        flags=re.IGNORECASE
    )

    if think_match:
        answer = answer[:think_match.start()]

    # ---------------------------------
    # Trường hợp <reasoning> không đóng
    # ---------------------------------

    reasoning_match = re.search(
        r"<reasoning>",
        answer,
        flags=re.IGNORECASE
    )

    if reasoning_match:
        answer = answer[:reasoning_match.start()]

    # ---------------------------------
    # Trường hợp <analysis> không đóng
    # ---------------------------------

    analysis_match = re.search(
        r"<analysis>",
        answer,
        flags=re.IGNORECASE
    )

    if analysis_match:
        answer = answer[:analysis_match.start()]

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
    # XÓA TÊN BOT
    # =========================

    bot_names = [
        "chị cá", "chica", "chicá",
        "chị ca", "cá ơi", "ca ơi",
    ]

    prompt_lower_check = prompt.lower()

    for name in bot_names:
        if prompt_lower_check.startswith(name):
            prompt = prompt[len(name):].strip(" ,.")
            break

    # =========================
    # LỆNH NHẠC
    # =========================

    prompt_lower = prompt.lower().strip()

    guild_id = message.guild.id if message.guild else None

    # --- PLAY ---
    if prompt_lower.startswith("play ") or prompt_lower.startswith("phát ") or prompt_lower.startswith("bật ") or prompt_lower.startswith("nghe ") or prompt_lower.startswith("cho nghe "):

        # Kiểm tra user có trong voice channel không
        if not message.author.voice or not message.author.voice.channel:
            await message.channel.send("Vào voice channel đi rồi chị phát cho.")
            return

        voice_channel = message.author.voice.channel

        # Lấy tên bài hát
        song_query = prompt
        for kw in ["play ", "phát ", "bật ", "nghe ", "cho nghe "]:
            if prompt_lower.startswith(kw):
                song_query = prompt[len(kw):]
                break

        if not song_query.strip():
            await message.channel.send("Gõ tên bài hát đi.")
            return

        await message.channel.send(f"🔍 Đang tìm: **{song_query}**...")

        try:
            # Tìm bài hát trên YouTube
            search_opts = {
                "format": "bestaudio/best",
                "quiet": True,
                "no_warnings": True,
                "default_search": "ytsearch1",
                "noplaylist": True,
                "extractor_args": {
                    "youtube": {
                        "player_client": ["ios", "web_creator"],
                    }
                },
                "http_headers": {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                },
            }

            with yt_dlp.YoutubeDL(search_opts) as ydl:
                info = await asyncio.to_thread(
                    ydl.extract_info,
                    f"ytsearch1:{song_query}",
                    download=False,
                )

                if not info or "entries" not in info or not info["entries"]:
                    await message.channel.send("Không tìm thấy bài hát nào.")
                    return

                entry = info["entries"][0]
                audio_url = entry.get("url")
                title = entry.get("title", "Unknown")

                if not audio_url:
                    await message.channel.send("Không lấy được link audio.")
                    return

        except Exception as e:
            print(f"LỖI YT-DLP: {e}", flush=True)
            await message.channel.send("Lỗi tìm nhạc rồi.")
            return

        # Thêm vào queue
        if guild_id not in music_queues:
            music_queues[guild_id] = []

        music_queues[guild_id].append({
            "title": title,
            "url": audio_url,
            "channel": message.channel,
        })

        await message.channel.send(f"🎵 Đã thêm: **{title}**")

        # Nếu bot chưa đang phát → phát ngay
        if not message.guild.voice_client or not message.guild.voice_client.is_playing():
            await play_next(guild_id)
        else:
            pos = len(music_queues[guild_id])
            await message.channel.send(f"📄 Thứ tự trong hàng: {pos}")

        return

    # --- STOP ---
    if prompt_lower in ["stop", "dừng", "tắt nhạc", "ngừng"]:
        if message.guild.voice_client:
            message.guild.voice_client.stop()
            music_queues[guild_id] = []
            await message.channel.send("⏹️ Đã dừng nhạc.")
        else:
            await message.channel.send("Chị đang phát gì đâu.")
        return

    # --- SKIP ---
    if prompt_lower in ["skip", "bỏ qua", "next", "đổi bài"]:
        if message.guild.voice_client and message.guild.voice_client.is_playing():
            message.guild.voice_client.stop()
            await message.channel.send("⏭️ Bỏ bài này.")
        else:
            await message.channel.send("Chị đang phát gì đâu.")
        return

    # --- QUEUE ---
    if prompt_lower in ["queue", "danh sách", "hàng", "xếp hàng"]:
        if guild_id not in music_queues or not music_queues[guild_id]:
            await message.channel.send("Hàng trống, không có bài nào.")
            return
        msg = "**Danh sách chờ:**\n"
        for i, song in enumerate(music_queues[guild_id], 1):
            msg += f"{i}. {song['title']}\n"
        await message.channel.send(msg[:2000])
        return

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

            "Không được hiển thị quá trình suy nghĩ, "
            "reasoning, phân tích nội bộ hoặc chain-of-thought "
            "cho người dùng. "

            "Chỉ trả về câu trả lời cuối cùng. "

            "/no_think"
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
        # XÓA THINKING
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