import asyncio
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import discord

from config import (
    ROLE_ID,
    KEYWORDS,
    HELP_KEYWORDS,
    EVENT_KEYWORDS,
    INVITE_KEYWORDS,
    MEMBER_KEYWORDS,
    POLL_KEYWORDS,
    REMIND_KEYWORDS,
    SUMMARY_KEYWORDS,
    ASSET_KEYWORDS,
    DAILY_KEYWORDS,
    GACHA_KEYWORDS,
    COLLECTION_KEYWORDS,
    PVP_KEYWORDS,
    PVP_RANK_KEYWORDS,
)
from game.pvp.ui import start_pvp_challenge, handle_pvp_rank, handle_card_info, is_in_pvp
from game.pvp.cards import find_card
from web_server import start_web_server
from db import init_db, get_gems
from points import maybe_award_points, handle_assets, handle_daily, EMBED_COLOR
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

    is_general_help = addressed and any(
        kw in content_lower for kw in HELP_KEYWORDS
    )
    if is_general_help:
        await handle_menu(message, bot)
        return

    is_event = addressed and any(kw in content_lower for kw in EVENT_KEYWORDS)
    if is_event:
        handled = await handle_event_creation(message, bot)
        if handled:
            return

    is_invite = addressed and any(kw in content_lower for kw in INVITE_KEYWORDS)
    if is_invite:
        await handle_invite(message, bot)
        return

    if addressed:
        is_member_list = any(kw in content_lower for kw in MEMBER_KEYWORDS)
        if is_member_list and message.guild:
            await handle_member_list(message, bot)
            return

        is_poll = any(kw in content_lower for kw in POLL_KEYWORDS)
        if is_poll:
            await handle_poll(message, bot)
            return

        is_remind = any(kw in content_lower for kw in REMIND_KEYWORDS)
        if is_remind:
            await handle_remind(message, bot)
            return

    is_summary = addressed and any(kw in content_lower for kw in SUMMARY_KEYWORDS)
    if is_summary:
        await handle_summary(message, bot)
        return

    is_gacha = addressed and any(kw in content_lower for kw in GACHA_KEYWORDS)
    if is_gacha:
        if is_in_pvp(message.author.id):
            await message.channel.send(
                "Em đang trong trận PvP, xong trận mới quay gacha được nhé 🐟",
                reference=message, mention_author=False,
            )
            return
        cl = message.content.lower()
        if "5" in cl:
            n = 5
        elif "1" in cl:
            n = 1
        else:
            n = None
        if n:
            await handle_gacha(message.channel, message.author, bot, n)
        else:
            pts = await get_gems(message.author.id)
            e = discord.Embed(
                title="🎰 Gacha Thẻ Genshin",
                description=f"Nguyên thạch hiện có: **{pts}💠**\nChọn số lượt quay:",
                color=EMBED_COLOR,
            )
            e.set_footer(text="1 lần = 50❖ • 5 lần = 250❖")
            view = GachaView(bot, message.author)
            g_msg = await message.channel.send(embed=e, view=view)
            view.message = g_msg
        return

    is_collection = addressed and any(kw in content_lower for kw in COLLECTION_KEYWORDS)
    if is_collection:
        await handle_collection(message.channel, message.author, bot)
        return

    is_pvp = addressed and any(kw in content_lower for kw in PVP_KEYWORDS)
    if is_pvp:
        cl = message.content.lower()
        if any(k in cl for k in PVP_RANK_KEYWORDS):
            await handle_pvp_rank(message, bot)
        else:
            await start_pvp_challenge(message, bot)
        return

    is_daily = addressed and any(kw in content_lower for kw in DAILY_KEYWORDS)
    if is_daily:
        await handle_daily(message, bot)
        return

    is_asset = addressed and any(kw in content_lower for kw in ASSET_KEYWORDS)
    if is_asset:
        await handle_assets(message, bot)
        return

    is_card_info = (
        addressed and "skill" in content_lower and (card := find_card(content_lower)) is not None
    )
    if is_card_info:
        await handle_card_info(message.channel, message.author, card)
        return

    if await handle_chat(message, bot):
        return
