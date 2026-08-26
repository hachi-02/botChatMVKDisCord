import asyncio
import re

import discord

from config import ROLE_ID, KEYWORDS, CHUI_KEYWORDS, PROVOCATION_KEYWORDS, MODEL_NAME
from ai import ai, get_system_prompt, clean_ai_response
from memory import add_message, get_history
from web_server import start_web_server

intents = discord.Intents.default()
intents.message_content = True

bot = discord.Client(intents=intents)


@bot.event
async def on_ready():
    print(f"Bot đã online: {bot.user}", flush=True)
    await start_web_server()
    print("Chị Cá đã sẵn sàng 🐟", flush=True)


@bot.event
async def on_message(message):

    print(
        f"NHẬN MESSAGE: {message.author}: {message.content}",
        flush=True
    )

    if message.author == bot.user:
        return

    if message.guild is None:
        return

    bot_mentioned = bot.user in message.mentions

    role_mentioned = any(
        role.id == ROLE_ID
        for role in message.role_mentions
    )

    content_lower = message.content.lower()

    if not bot_mentioned and not role_mentioned:
        if not any(kw in content_lower for kw in KEYWORDS):
            return

    is_chui = any(kw in content_lower for kw in CHUI_KEYWORDS)
    is_provoked = any(kw in content_lower for kw in PROVOCATION_KEYWORDS)

    prompt = message.content

    if bot.user:
        prompt = prompt.replace(bot.user.mention, "")
        prompt = prompt.replace(f"<@{bot.user.id}>", "")
        prompt = prompt.replace(f"<@!{bot.user.id}>", "")

    for role in message.role_mentions:
        prompt = prompt.replace(role.mention, "")

    prompt = prompt.strip()

    sender_name = (
        message.author.display_name
        or message.author.name
    )

    if is_chui:
        prompt = f"[CHỬI] {prompt}"
    elif is_provoked:
        prompt = f"[CHỌC GHẸO] {prompt}"

    if not prompt:
        await message.channel.send("M gọi Chị Cá đó hả? 🐟")
        return

    channel_id = message.channel.id

    add_message(channel_id, "user", f"[{sender_name}]: {prompt}")

    try:
        print(f"GỬI AI: {prompt}", flush=True)

        system_prompt = get_system_prompt(sender_name)

        response = await asyncio.to_thread(
            ai.chat.completions.create,
            model=MODEL_NAME,
            reasoning_effort="default",
            max_tokens=4096,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
                }
            ] + get_history(channel_id),
        )

        ai_message = response.choices[0].message
        finish_reason = response.choices[0].finish_reason
        print("USAGE:", response.usage, flush=True)

        print("AI RAW CONTENT:", repr(ai_message.content), flush=True)
        print("FINISH REASON:", finish_reason, flush=True)

        reasoning_content = getattr(ai_message, "reasoning_content", None)
        if reasoning_content:
            print("AI REASONING:", repr(reasoning_content), flush=True)

        answer = ai_message.content or ""
        answer = clean_ai_response(answer)

        # Fix emoji format thiếu <
        answer = re.sub(r"(?<!<):([a-z]+:\d+>)", r"<:\1", answer)

        print("AI CLEAN:", repr(answer), flush=True)

        if len(answer) > 2000:
            answer = answer[:1997] + "..."

        if not answer.strip():
            if finish_reason == "length":
                await message.channel.send(
                    "Câu này hơi dài, chị bị cắt ngang lúc đang trả lời rồi 😅 "
                    "em hỏi ngắn gọn lại giúp chị nhé."
                )
            else:
                await message.channel.send("Chị Cá không biết trả lời sao 😅")
            return

        print(f"AI: {answer}", flush=True)

        await message.channel.send(answer)

        add_message(channel_id, "assistant", answer)

    except Exception as e:
        print(f"LỖI AI: {type(e).__name__}: {e}", flush=True)
        await message.channel.send("Chị Cá bị lỗi khi gọi AI rồi 😭")
