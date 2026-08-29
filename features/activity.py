import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

import discord

from config import (
    IDLE_HOURS,
    IDLE_CHECK_INTERVAL,
    IDLE_MAX_PER_DAY,
    IDLE_SCAN_LIMIT,
    IDLE_CHANNEL_NAMES,
)
from ai import generate_ask

guild_last_human = {}
channel_last_human = {}
idle_sent_dates = {}
idle_last_sent = {}


def note_activity(message):
    now = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))
    guild_last_human[message.guild.id] = now
    if isinstance(message.channel, discord.TextChannel):
        channel_last_human[message.channel.id] = now


async def scan_server_history(bot):
    await bot.wait_until_ready()
    for guild in bot.guilds:
        try:
            last = None
            for ch in guild.text_channels:
                try:
                    async for m in ch.history(limit=IDLE_SCAN_LIMIT):
                        if m.author == bot.user:
                            continue
                        if last is None or m.created_at > last:
                            last = m.created_at
                        cur = channel_last_human.get(ch.id)
                        if cur is None or m.created_at > cur:
                            channel_last_human[ch.id] = m.created_at
                except Exception:
                    continue
            if last is not None and (
                guild_last_human.get(guild.id) is None
                or last > guild_last_human[guild.id]
            ):
                guild_last_human[guild.id] = last
        except Exception as e:
            print(f"LỖI SCAN HISTORY {guild.name}: {type(e).__name__}: {e}", flush=True)


async def idle_checker(bot):
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            now = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))
            today = now.date()
            for guild in bot.guilds:
                last = guild_last_human.get(guild.id)
                if last is None:
                    continue
                idle = (now - last).total_seconds() / 3600
                if idle < IDLE_HOURS:
                    continue
                if idle_last_sent.get(guild.id) is not None and \
                        (now - idle_last_sent[guild.id]).total_seconds() / 3600 < IDLE_HOURS:
                    continue
                sent_day, sent_count = idle_sent_dates.get(guild.id, (None, 0))
                if sent_day != today:
                    sent_count = 0
                if sent_count >= IDLE_MAX_PER_DAY:
                    continue
                target = discord.utils.find(
                    lambda c: isinstance(c, discord.TextChannel)
                    and c.name.casefold() in [n.casefold() for n in IDLE_CHANNEL_NAMES],
                    guild.text_channels,
                )
                if target is None:
                    continue
                perms = target.permissions_for(guild.me)
                if not (perms.send_messages and perms.view_channel):
                    continue
                text = generate_ask(guild.name, idle)
                if not text:
                    continue
                if len(text) > 1900:
                    text = text[:1897] + "..."
                await target.send(text)
                idle_last_sent[guild.id] = now
                idle_sent_dates[guild.id] = (today, sent_count + 1)
                print(f"IDLE ASK → {guild.name}: {text}", flush=True)
        except Exception as e:
            print(f"LỖI IDLE_CHECKER: {type(e).__name__}: {e}", flush=True)
        await asyncio.sleep(IDLE_CHECK_INTERVAL)
