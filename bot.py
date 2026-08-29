import asyncio
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import discord

from config import (
    ROLE_ID,
    KEYWORDS,
    PVP_RANK_KEYWORDS,
)
from game.pvp.ui import start_pvp_challenge, handle_pvp_rank, handle_card_info, handle_show_card, is_in_pvp
from game.pvp.cards import find_card
from web_server import start_web_server
from db import init_db, get_gems
from points import maybe_award_points, handle_assets, handle_daily
from gacha.gacha import handle_gacha, handle_collection, GachaView
from features.scheduler import (
    handle_event_creation,
    handle_remind,
    remind_checker,
    event_reminder_checker,
)
from features.activity import note_activity, scan_server_history, idle_checker
from features.server_tools import (
    handle_menu,
    handle_invite,
    handle_member_list,
    handle_poll,
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
    bot.loop.create_task(scan_server_history(bot))
    bot.loop.create_task(idle_checker(bot))
    if not getattr(bot, "_db_inited", False):
        try:
            await init_db()
            bot._db_inited = True
        except Exception as e:
            print(f"LỖI INIT DB: {type(e).__name__}: {e}", flush=True)
    print("Chị Cá đã sẵn sàng 🐟", flush=True)


@bot.event
async def on_member_join(member):
    channel = member.guild.system_channel
    if channel:
        await channel.send(
            f"Chào em {member.mention} đến với server! 🐟 "
            f"Gọi chị Cá nếu cần gì nhé."
        )


@bot.event
async def on_message(message):

    print(f"NHẬN MESSAGE: {message.author}: {message.content}", flush=True)

    if message.author == bot.user:
        return

    if message.guild is None:
        return

    note_activity(message)

    await maybe_award_points(message, bot)

    bot_mentioned = bot.user in message.mentions

    role_mentioned = any(role.id == ROLE_ID for role in message.role_mentions)

    content_lower = message.content.lower()

    addressed = (
        bot_mentioned
        or role_mentioned
        or any(kw in content_lower for kw in KEYWORDS)
    )

    # ---- Dispatch lệnh: `chica <lenh>` (thứ tự cứng, chica ở đầu) ----
    cmd_match = re.match(r"^\s*chica\b\s*(.*)$", content_lower)
    if cmd_match:
        cmd = cmd_match.group(1).strip()
        cmdl = cmd.lower()
        tokens = cmd.split()
        t0 = tokens[0].lower() if tokens else ""

        if t0 == "member":
            await handle_member_list(message, bot)
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

        if t0 == "bag":
            await handle_assets(message, bot)
            return

        if t0 == "inventory":
            await handle_collection(message.channel, message.author, bot)
            return

        if t0 == "gacha":
            if is_in_pvp(message.author.id):
                await message.channel.send(
                    "Em đang trong trận PvP, xong trận mới quay gacha được nhé 🐟",
                    reference=message, mention_author=False,
                )
                return
            if "5" in cmdl:
                n = 5
            elif "1" in cmdl:
                n = 1
            else:
                n = None
            if n:
                await handle_gacha(message.channel, message.author, bot, n)
            else:
                pts = await get_gems(message.author.id)
                view = GachaView(bot, message.author, pts)
                g_msg = await message.channel.send(view=view)
                view.message = g_msg
            return

        if t0 == "show" and (card := find_card(cmd)) is not None:
            await handle_show_card(message.channel, card)
            return

        if t0 == "info" and (card := find_card(cmd)) is not None:
            await handle_card_info(message.channel, message.author, card)
            return

        if t0 == "menu":
            await handle_menu(message, bot)
            return

        if t0 == "vote":
            await handle_poll(message, bot)
            return

        if t0 == "daily":
            await handle_daily(message, bot)
            return

        if t0 == "pvp":
            if any(k in cmdl for k in PVP_RANK_KEYWORDS):
                await handle_pvp_rank(message, bot)
            else:
                await start_pvp_challenge(message, bot)
            return

        if cmdl.startswith("voice in") or cmdl == "voicein":
            await handle_voice_join(message, bot)
            return

        if cmdl.startswith("voice out") or cmdl == "voiceout":
            await handle_voice_leave(message, bot)
            return

    if await handle_chat(message, bot):
        return
