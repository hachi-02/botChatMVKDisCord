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
    author_vc = message.author.voice
    if author_vc is None or author_vc.channel is None:
        await message.channel.send(
            "Em phải vào kênh thoại trước đã, chị vào sau nhé 🐟",
            reference=message, mention_author=False,
        )
        return
    channel = author_vc.channel
    voice = _bot_voice(bot, message.guild)
    if voice is not None and voice.is_connected():
        await message.channel.send(
            f"Chị đang ở trong **{voice.channel.name}** rồi nha 🐟",
            reference=message, mention_author=False,
        )
        return
    try:
        voice = await channel.connect()
        voice.play(_SilenceSource())
        await message.channel.send(
            f"✅ Chị vào **{channel.name}** giữ chỗ cho em 🐟",
            reference=message, mention_author=False,
        )
    except Exception as e:
        await message.channel.send(
            f"Lỗi vào voice: {type(e).__name__}",
            reference=message, mention_author=False,
        )


async def handle_voice_leave(message, bot):
    voice = _bot_voice(bot, message.guild)
    if voice is None or not voice.is_connected():
        await message.channel.send(
            "Chị chưa ở trong kênh thoại nào cả 🐟",
            reference=message, mention_author=False,
        )
        return
    try:
        await voice.disconnect()
        await message.channel.send(
            "👋 Chị rời kênh thoại đây. Gọi chị `voicein` nếu cần giữ chỗ nhé 🐟",
            reference=message, mention_author=False,
        )
    except Exception as e:
        await message.channel.send(
            f"Lỗi rời voice: {type(e).__name__}",
            reference=message, mention_author=False,
        )
