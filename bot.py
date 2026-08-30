import asyncio
import random
import re
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import discord

from config import (
    ROLE_ID,
    KEYWORDS,
    PVP_RANK_KEYWORDS,
)

pending_kicks = {}  # user_id -> {"target_id": int, "timestamp": float}

from game.pvp.ui import start_pvp_challenge, handle_pvp_rank, handle_card_info, handle_show_card, is_in_pvp
from game.pvp.cards import find_card
from web_server import start_web_server
from db import (
    init_db, get_gems, log_message,
    jail_user, unjail_user, get_jail_state, set_jail_sentence, increment_jail_done
)
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
    handle_hug,
)
from features.chat import handle_chat, handle_summary
from features.voice import handle_voice_join, handle_voice_leave
from features.report import weekly_report_checker

intents = discord.Intents.default()
intents.members = True
intents.presences = True
intents.message_content = True

bot = discord.Client(intents=intents)

# Danh sách mẫu các câu chép phạt công ích
JAIL_SENTENCES = [
    "Tôi hứa từ nay sẽ chấp hành đúng nội quy server và không vi phạm nữa.",
    "Tôn trọng thành viên khác là tôn trọng chính bản thân mình.",
    "Lao động là quang vinh, chép phạt giúp tâm tính bình hòa.",
    "Chị Cá rất hiền lành nhưng nội quy server thì rất nghiêm túc.",
    "Tôi sẽ suy nghĩ kỹ trước khi phát ngôn hoặc hành động trên server.",
    "Một lần bất tín, vạn lần bất tin, tôi sẽ cải tạo tốt để làm lại từ đầu."
]

async def get_or_create_jail_role(guild: discord.Guild) -> discord.Role:
    """Lấy hoặc tự động tạo Role Tù Nhân với quyền ẩn toàn bộ kênh."""
    role = discord.utils.get(guild.roles, name="Tù Nhân - Chép Phạt")
    if not role:
        try:
            role = await guild.create_role(
                name="Tù Nhân - Chép Phạt",
                color=discord.Color.dark_gray(),
                reason="Tạo role tự động cho hệ thống Nhà tù công ích"
            )
        except Exception as e:
            print(f"LỖI TẠO ROLE JAIL: {e}", flush=True)
            return None

    # Khóa toàn bộ kênh thường: Ẩn kênh (view_channel=False) & Tắt gửi tin
    for ch in guild.channels:
        if ch.name != "phong-chep-phat":
            try:
                await ch.set_permissions(role, view_channel=False, send_messages=False)
            except Exception:
                pass

    return role


@bot.event
async def on_ready():
    print(f"Bot đã online: {bot.user}", flush=True)
    await start_web_server()
    bot.loop.create_task(remind_checker(bot))
    bot.loop.create_task(event_reminder_checker(bot))
    bot.loop.create_task(scan_server_history(bot))
    bot.loop.create_task(idle_checker(bot))
    bot.loop.create_task(weekly_report_checker(bot))
    if not getattr(bot, "_db_inited", False):
        try:
            await init_db()
            bot._db_inited = True
        except Exception as e:
            print(f"LỖI INIT DB: {type(e).__name__}: {e}", flush=True)
    print("Chị Cá đã sẵn sàng 🐟", flush=True)


@bot.event
async def on_member_join(member):
    # Kiểm tra xem thành viên mới vào có đang thụ án trong Database không (Chống trốn trại)
    jail_info = await get_jail_state(member.id)
    if jail_info:
        jail_role = await get_or_create_jail_role(member.guild)
        try:
            # Tự động tháo các role khác và gán lại role Tù nhân
            roles_to_remove = [r for r in member.roles if not r.is_default() and r != jail_role]
            if roles_to_remove:
                await member.remove_roles(*roles_to_remove)
            if jail_role:
                await member.add_roles(jail_role)
            print(f"Phát hiện tù nhân {member.name} quay lại server, đã tái áp đặt án phạt!", flush=True)
        except Exception as e:
            print(f"Lỗi khi gán lại role jail cho member join: {e}", flush=True)
        return

    # Lời chào mừng thành viên mới bình thường
    guild = member.guild
    channel = discord.utils.get(guild.text_channels, name="chat-chit") or guild.system_channel
    if channel is None:
        channel = discord.utils.find(
            lambda c: c.permissions_for(guild.me).send_messages,
            guild.text_channels,
        )
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

    # ==========================================
    # KIỂM TRA HỆ THỐNG TÙ NHÂN CHÉP PHẠT (JAIL)
    # ==========================================
    jail_info = await get_jail_state(message.author.id)
    if jail_info:
        # Nếu đang ở trong tù, chặn tất cả tin nhắn ngoài kênh phong-chep-phat
        if message.channel.name != "phong-chep-phat":
            try:
                await message.delete()
            except Exception:
                pass
            return

        # Đang ở trong kênh chép phạt
        current_sentence = jail_info.get("current_sentence")

        # Trường hợp chưa có câu chép phạt hiện tại -> Giao câu mới
        if not current_sentence:
            new_sentence = random.choice(JAIL_SENTENCES)
            await set_jail_sentence(message.author.id, new_sentence)
            await message.channel.send(
                f"⛓️ **TÙ NHÂN {message.author.mention}** [{jail_info['done_count']}/{jail_info['target_count']}]\n"
                f"Hãy chép lại chính xác câu sau đây để giảm án:\n"
                f"```\n{new_sentence}\n```",
                reference=message, mention_author=False
            )
            return

        # Trường hợp đã có câu chép phạt -> Kiểm tra nội dung chép
        if message.content.strip() == current_sentence.strip():
            # Chép đúng
            updated = await increment_jail_done(message.author.id)
            if updated and updated["done_count"] >= updated["target_count"]:
                # Đã hoàn thành đủ chỉ tiêu -> Thả tù
                await unjail_user(message.author.id)
                jail_role = discord.utils.get(message.guild.roles, name="Tù Nhân - Chép Phạt")
                if jail_role and jail_role in message.author.roles:
                    try:
                        await message.author.remove_roles(jail_role)
                    except Exception:
                        pass
                
                # Khôi phục các role cũ
                roles_to_add = [
                    message.guild.get_role(rid) 
                    for rid in updated["original_roles"] 
                    if message.guild.get_role(rid) is not None
                ]
                if roles_to_add:
                    try:
                        await message.author.add_roles(*roles_to_add)
                    except Exception as e:
                        print(f"Không thể khôi phục role cho {message.author}: {e}", flush=True)

                await message.channel.send(
                    f"🎉 **ĐÃ HOÀN THÀNH MÃ HẠN TÙ!**\n"
                    f"Chúc mừng {message.author.mention} đã chép phạt xong **{updated['target_count']}** câu và được khôi phục quyền công dân! Hãy giữ mình nhé 🐟",
                    reference=message, mention_author=False
                )
            else:
                # Giao tiếp câu tiếp theo
                next_sentence = random.choice(JAIL_SENTENCES)
                await set_jail_sentence(message.author.id, next_sentence)
                await message.channel.send(
                    f"✅ **Đúng!** Tiến độ: [{updated['done_count']}/{updated['target_count']}]\n"
                    f"Câu tiếp theo của em:\n```\n{next_sentence}\n```",
                    reference=message, mention_author=False
                )
        else:
            # Chép sai
            await message.channel.send(
                f"❌ Chép sai rồi! Hãy chép lại **chính xác từng ký tự**:\n```\n{current_sentence}\n```",
                reference=message, mention_author=False
            )
        return

    note_activity(message)

    await log_message(message.author.id, message.channel.id, message.guild.id)

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

        # LỆNH JAIL (NHỐT TÙ CHÉP PHẠT)
        if t0 == "jail":
            if not message.author.guild_permissions.administrator:
                await message.channel.send(
                    "Chỉ admin mới có quyền nhốt tù công ích nhé 🐟",
                    reference=message, mention_author=False
                )
                return

            if not message.mentions:
                await message.channel.send(
                    "Cú pháp: `chica jail @người <số_câu>`\nVí dụ: `chica jail @User 10`",
                    reference=message, mention_author=False
                )
                return

            target = message.mentions[0]
            if target == bot.user:
                await message.channel.send("Em không thể nhốt chính em cá nha 🐟", reference=message, mention_author=False)
                return

            # Lấy số câu chép phạt (mặc định 5 câu nếu không nhập)
            target_count = 5
            for token in tokens[1:]:
                if token.isdigit():
                    target_count = int(token)
                    break

            # Lưu lại danh sách role cũ (trừ role @everyone)
            original_roles = [r.id for r in target.roles if not r.is_default()]
            
            # Đưa vào DB
            await jail_user(target.id, target_count, original_roles)

            # Lấy hoặc tạo Role Tù nhân
            jail_role = await get_or_create_jail_role(message.guild)

            # Tìm hoặc tạo kênh #phong-chep-phat
            jail_channel = discord.utils.get(message.guild.text_channels, name="phong-chep-phat")
            if not jail_channel:
                try:
                    overwrites = {
                        message.guild.default_role: discord.PermissionOverwrite(view_channel=False), # Dân thường không thấy phòng tù
                        jail_role: discord.PermissionOverwrite(view_channel=True, send_messages=True), # Tù nhân thấy và nhắn được
                        message.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True) # Bot thấy
                    }
                    jail_channel = await message.guild.create_text_channel("phong-chep-phat", overwrites=overwrites)
                except Exception as e:
                    jail_channel = message.channel
            else:
                if jail_role:
                    await jail_channel.set_permissions(jail_role, view_channel=True, send_messages=True)

            # Gán role Tù nhân và tháo các role khác
            try:
                roles_to_remove = [r for r in target.roles if not r.is_default() and r != jail_role]
                if roles_to_remove:
                    await target.remove_roles(*roles_to_remove)
                if jail_role:
                    await target.add_roles(jail_role)
            except Exception as e:
                print(f"Lỗi khi tháo/gán role jail: {e}", flush=True)

            await message.channel.send(
                f"🚨 {target.mention} đã bị nhốt vào nhà tù công ích với **{target_count} câu chép phạt**!\n"
                f"Hãy di chuyển đến kênh {jail_channel.mention} để thực hiện nghĩa vụ.",
                reference=message, mention_author=False
            )
            return

        # LỆNH UNJAIL (THẢ TÙ TRƯỚC THỜI HẠN)
        if t0 == "unjail":
            if not message.author.guild_permissions.administrator:
                await message.channel.send(
                    "Chỉ admin mới có quyền thả tù trước thời hạn 🐟",
                    reference=message, mention_author=False
                )
                return

            if not message.mentions:
                await message.channel.send(
                    "Cú pháp: `chica unjail @người`",
                    reference=message, mention_author=False
                )
                return

            target = message.mentions[0]
            jail_info = await get_jail_state(target.id)
            if not jail_info:
                await message.channel.send(
                    f"{target.mention} hiện không ở trong tù 🐟",
                    reference=message, mention_author=False
                )
                return

            # Xóa trong DB
            await unjail_user(target.id)

            # Tháo Role Tù nhân & Trả lại Role cũ
            jail_role = discord.utils.get(message.guild.roles, name="Tù Nhân - Chép Phạt")
            if jail_role and jail_role in target.roles:
                try:
                    await target.remove_roles(jail_role)
                except Exception:
                    pass

            roles_to_add = [
                message.guild.get_role(rid) 
                for rid in jail_info["original_roles"] 
                if message.guild.get_role(rid) is not None
            ]
            if roles_to_add:
                try:
                    await target.add_roles(*roles_to_add)
                except Exception as e:
                    print(f"Lỗi khôi phục role: {e}", flush=True)

            await message.channel.send(
                f"🔓 {target.mention} đã được Admin đặc xá và thả tự do trước thời hạn!",
                reference=message, mention_author=False
            )
            return

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

        if t0 == "kick":
            if not message.mentions:
                await message.channel.send(
                    "Em cần một người để kick nhé 🐟\nDùng: `chica kick @người`",
                    reference=message, mention_author=False,
                )
                return

            target = message.mentions[0]
            author = message.author

            # Không tự kick bot chính
            if target == bot.user:
                await message.channel.send(
                    "Em không thể kick chính em cá nha 🐟",
                    reference=message, mention_author=False,
                )
                return

            # Kiểm tra quyền admin
            if not message.author.guild_permissions.administrator:
                await message.channel.send(
                    "Chỉ admin mới có quyền kick 🐟",
                    reference=message, mention_author=False,
                )
                return

            # Kiểm tra role hierarchy: author phải có role cao hơn target
            if target.top_role.position >= author.top_role.position:
                await message.channel.send(
                    f"Em không có quyền kick {target.mention} vì role của em thấp hơn hoặc bằng 🐟",
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
                f"Gõ `chica yes` để xác nhận hoặc `chica no` để hủy (hết 30s tự hủy).",
                reference=message, mention_author=False,
            )
            return

        if t0 == "yes":
            # Xử lý xác nhận kick
            if message.author.id in pending_kicks:
                data = pending_kicks.pop(message.author.id)
                elapsed = time.time() - data["timestamp"]
                # Kiểm tra timeout 30s
                if elapsed > 30:
                    await message.channel.send(
                        "⏰ Thời gian chờ hết 30s, lệnh kick đã tự hủy 🐟",
                        reference=message, mention_author=False,
                    )
                    return
                # Thực hiện kick
                target = discord.utils.get(message.guild.members, id=data["target_id"])
                if target:
                    try:
                        await target.kick(reason=f"Kick bởi {message.author.name} (xác nhận via chica yes)")
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
                        "Không tìm thấy người dùng này trong server 🐟",
                        reference=message, mention_author=False,
                    )
            else:
                await message.channel.send(
                    "Em chưa có lệnh kick nào đang chờ duyệt nhé 🐟",
                    reference=message, mention_author=False,
                )
            return

        if t0 == "no":
            # Hủy lệnh kick
            if message.author.id in pending_kicks:
                pending_kicks.pop(message.author.id)
                await message.channel.send(
                    "🚫 Lệnh kick đã bị hủy nhé 🐟",
                    reference=message, mention_author=False,
                )
            else:
                await message.channel.send(
                    "Em chưa có lệnh kick nào đang chờ duyệt nhé 🐟",
                    reference=message, mention_author=False,
                )
            return

    if await handle_chat(message, bot):
        return