import asyncio
import traceback

import discord

SILENCE_FRAME = b"\x00" * 3840


class _SilenceSource(discord.AudioSource):
    def read(self):
        return SILENCE_FRAME

    def cleanup(self):
        pass


def _bot_voice(bot, guild):
    for vc in bot.voice_clients:
        if vc.guild.id == guild.id:
            return vc
    return None


async def handle_voice_join(message, bot):
    print("VOICE_JOIN: bắt đầu xử lý", flush=True)
    try:
        author_vc = message.author.voice
        if author_vc is None or author_vc.channel is None:
            await message.channel.send(
                "Em phải vào kênh thoại trước đã, chị vào sau nhé 🐟",
                reference=message, mention_author=False,
            )
            return
        channel = author_vc.channel
        print(f"VOICE_JOIN: kênh '{channel.name}' (id={channel.id})", flush=True)
        print(f"VOICE_JOIN: guild {message.guild.name} id={message.guild.id}", flush=True)

        # Kiểm tra opus có load được không
        print(f"VOICE_JOIN: discord.opus.is_loaded() = {discord.opus.is_loaded()}", flush=True)
        print(f"VOICE_JOIN: nacl -> {getattr(discord, 'crypto', None)}", flush=True)

        voice = _bot_voice(bot, message.guild)
        if voice is not None and voice.is_connected():
            await message.channel.send(
                f"Chị đang ở trong **{voice.channel.name}** rồi nha 🐟",
                reference=message, mention_author=False,
            )
            return

        print("VOICE_JOIN: đang gọi channel.connect() ...", flush=True)
        voice = await channel.connect()
        print("VOICE_JOIN: connect() thành công, voice.is_connected =",
              voice.is_connected(), flush=True)
        print("VOICE_JOIN: đang gọi voice.play(_SilenceSource()) ...", flush=True)
        voice.play(_SilenceSource())
        print("VOICE_JOIN: voice.play() thành công", flush=True)
        await asyncio.sleep(1)
        print("VOICE_JOIN: sau 1s, voice.is_playing =", voice.is_playing(), flush=True)
        await message.channel.send(
            f"✅ Chị vào **{channel.name}** giữ chỗ cho em 🐟",
            reference=message, mention_author=False,
        )
    except Exception as e:
        print("=" * 60, flush=True)
        print(f"VOICE_JOIN EXCEPTION: {type(e).__name__}: {e!r}", flush=True)
        traceback.print_exc()
        print("=" * 60, flush=True)
        await message.channel.send(
            f"Lỗi vào voice: {type(e).__name__}: {e}",
            reference=message, mention_author=False,
        )


async def handle_voice_leave(message, bot):
    try:
        voice = _bot_voice(bot, message.guild)
        if voice is None or not voice.is_connected():
            await message.channel.send(
                "Chị chưa ở trong kênh thoại nào cả 🐟",
                reference=message, mention_author=False,
            )
            return
        await voice.disconnect()
        await message.channel.send(
            "👋 Chị rời kênh thoại đây. Gọi chị `voicein` nếu cần giữ chỗ nhé 🐟",
            reference=message, mention_author=False,
        )
    except Exception as e:
        print("=" * 60, flush=True)
        print(f"VOICE_LEAVE EXCEPTION: {type(e).__name__}: {e!r}", flush=True)
        traceback.print_exc()
        print("=" * 60, flush=True)
        await message.channel.send(
            f"Lỗi rời voice: {type(e).__name__}: {e}",
            reference=message, mention_author=False,
        )
