import re
import time

import discord

from config import (
    ROLE_ID,
    KEYWORDS,
)

pending_kicks = {}  # user_id -> {"target_id": int, "timestamp": float}

from web_server import start_web_server
from features.scheduler import (
    handle_event_creation,
    handle_remind,
    remind_checker,
    event_reminder_checker,
)
from features.server_tools import (
    handle_menu,
    handle_invite,
    handle_member_list,
    handle_poll,
    handle_hug,
)
from features.chat import handle_chat, handle_summary
from features.voice import handle_voice_join, handle_voice_leave

intents = discord.Intents.default()
intents.members = True
intents.presences = True
intents.message_content = True

bot = discord.Client(intents=intents)


@bot.event
async def on_ready():
    print(f"Bot đã online: {bot.user}", flush=True)
    await start_web_server()
    bot.loop.create_task(remind_checker(bot))
    bot.loop.create_task(event_reminder_checker(bot))
    print("Chị Đại Mavuika đã sẵn sàng 🔥", flush=True)


@bot.event
async def on_member_join(member):
    # Lời chào mừng thành viên mới
    guild = member.guild
    channel = discord.utils.get(guild.text_channels, name="chat-chit") or guild.system_channel
    if channel is None:
        channel = discord.utils.find(
            lambda c: c.permissions_for(guild.me).send_messages,
            guild.text_channels,
        )
    if channel:
        await channel.send(
            f"Chào em {member.mention} đến với server! 🔥 "
            f"Gọi chị đại mavuika nếu cần gì nhé."
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

    addressed = (
        bot_mentioned
        or role_mentioned
        or any(kw in content_lower for kw in KEYWORDS)
    )

    # ---- Dispatch lệnh: `mvk <lenh>` (thứ tự cứng, mvk ở đầu) ----
    cmd_match = re.match(r"^\s*mvk\b\s*(.*)$", content_lower)
    if cmd_match:
        cmd = cmd_match.group(1).strip()
        cmdl = cmd.lower()
        tokens = cmd.split()
        t0 = tokens[0].lower() if tokens else ""

        if t0 == "member":
            await handle_member_list(message, bot)
            return

        if t0 == "hug":
            await handle_hug(message, bot)
            return

        if t0 == "search":
            await handle_chat(message, bot)
            return

        if t0 == "summary":
            await handle_summary(message, bot)
            return

        if t0 == "remind":
            await handle_remind(message, bot)
            return

        if t0 == "make" or t0 == "event":
            await handle_event_creation(message, bot)
            return

        if t0 == "link":
            await handle_invite(message, bot)
            return

        if t0 == "menu":
            await handle_menu(message, bot)
            return

        if t0 == "vote":
            await handle_poll(message, bot)
            return

        if cmdl.startswith("voice in") or cmdl == "voicein":
            await handle_voice_join(message, bot)
            return

        if cmdl.startswith("voice out") or cmdl == "voiceout":
            await handle_voice_leave(message, bot)
            return

        if t0 == "kick":
            if not message.mentions:
                await message.channel.send(
                    "Em cần một người để kick nhé 🔥\nDùng: `mvk kick @người`",
                    reference=message, mention_author=False,
                )
                return

            target = message.mentions[0]
            author = message.author

            # Không tự kick bot chính
            if target == bot.user:
                await message.channel.send(
                    "Em không thể kick chính em cá nha 🔥",
                    reference=message, mention_author=False,
                )
                return

            # Kiểm tra quyền admin
            if not message.author.guild_permissions.administrator:
                await message.channel.send(
                    "Chỉ admin mới có quyền kick 🔥",
                    reference=message, mention_author=False,
                )
                return

            # Kiểm tra role hierarchy: author phải có role cao hơn target
            if target.top_role.position >= author.top_role.position:
                await message.channel.send(
                    f"Em không có quyền kick {target.mention} vì role của em thấp hơn hoặc bằng 🔥",
                    reference=message, mention_author=False,
                )
                return

            # Kiểm tra quyền bot kick members
            if not message.guild.me.guild_permissions.kick_members:
                await message.channel.send(
                    "Em thiếu quyền **Kick Members** để thực hiện lệnh này 😭",
                    reference=message, mention_author=False,
                )
                return

            # Lưu trạng thái chờ xác nhận kèm timestamp
            pending_kicks[author.id] = {
                "target_id": target.id,
                "timestamp": time.time(),
            }
            await message.channel.send(
                f"🔔 {author.mention}, em có muốn kick {target.mention} không?\n"
                f"Gõ `mvk yes` để xác nhận hoặc `mvk no` để hủy (hết 30s tự hủy).",
                reference=message, mention_author=False,
            )
            return

        if t0 == "yes":
            # Xử lý xác nhận kick
            if message.author.id in pending_kicks:
                data = pending_kicks.pop(message.author.id)
                elapsed = time.time() - data["timestamp"]
                if elapsed > 30:
                    await message.channel.send(
                        "⏰ Thời gian chờ hết 30s, lệnh kick đã tự hủy 🔥",
                        reference=message, mention_author=False,
                    )
                    return
                target = discord.utils.get(message.guild.members, id=data["target_id"])
                if target:
                    try:
                        await target.kick(reason=f"Kick bởi {message.author.name} (xác nhận via mvk yes)")
                        await message.channel.send(
                            f"✅ {target.mention} đã được kick khỏi server!",
                            reference=message, mention_author=False,
                        )
                    except Exception as e:
                        await message.channel.send(
                            f"❌ Không thể kick {target.mention}: {type(e).__name__}: {e}",
                            reference=message, mention_author=False,
                        )
                else:
                    await message.channel.send(
                        "Không tìm thấy người dùng này trong server 🔥",
                        reference=message, mention_author=False,
                    )
            else:
                await message.channel.send(
                    "Em chưa có lệnh kick nào đang chờ duyệt nhé 🔥",
                    reference=message, mention_author=False,
                )
            return

        if t0 == "no":
            # Hủy lệnh kick
            if message.author.id in pending_kicks:
                pending_kicks.pop(message.author.id)
                await message.channel.send(
                    "🚫 Lệnh kick đã bị hủy nhé 🔥",
                    reference=message, mention_author=False,
                )
            else:
                await message.channel.send(
                    "Em chưa có lệnh kick nào đang chờ duyệt nhé 🔥",
                    reference=message, mention_author=False,
                )
            return

    if await handle_chat(message, bot):
        return