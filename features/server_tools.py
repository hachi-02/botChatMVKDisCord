import re

import discord

from points import EMBED_COLOR, LEVELUP_GIF

NUMBER_EMOJIS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

MENU_PAGES = [
    (
        "💬 Trò chuyện & Thông tin",
        [
            ("💬 Nói chuyện", "Gọi `chị cá` hoặc tag chị"),
            ("🔍 Tìm web", "`chị cá` + \"tìm\", \"là ai\", \"khi nào\"..."),
            ("👥 Thành viên online", "`chị cá` + \"ai đang online\""),
            ("🔎 Tóm tắt", "`chị cá` + `tóm tắt 1 tiếng` / `tóm tắt 30 tin`"),
        ],
    ),
    (
        "🛠️ Công cụ Server",
        [
            ("📊 Vote", "`chị cá` + `vote Câu hỏi? | chọn 1 | chọn 2`"),
            ("⏰ Nhắc", "`chị cá` + `nhắc em 7h học bài`"),
            ("📅 Điểm danh", "`chị cá` + `daily` (mỗi ngày +10💠 +500🪙)"),
            ("📅 Sự kiện", "`chị cá tạo sự kiện` + `Tên | thời gian | mô tả | địa điểm`"),
            ("🔗 Lời mời", "`chị cá` + `tạo link mời`"),
        ],
    ),
    (
        "🎮 Trò chơi & Điểm",
        [
            ("💠 Tài sản", "`chị cá` + `tài sản` (xem nguyên thạch / mora / cấp)"),
            ("🎴 Gacha", "`chị cá` + `gacha` / `gacha 1` / `gacha 5` (50❖ / 250❖)"),
            ("🗃️ Kho thẻ", "`chị cá` + `kho` (xem các thẻ đã có)"),
            ("⚔️ PvP", "`chị cá` + `pvp @người_chơi` (3v3 turn-based, ELO)"),
            ("🏆 Xếp hạng PvP", "`chị cá` + `pvp điểm` / `pvp top`"),
            ("ℹ️ Thông tin thẻ", "`chị cá` + `skill + tên` (vd: `chị cá skill skirk` — xem thẻ đã sở hữu)"),
        ],
    ),
]


def _menu_embed(bot, page=0):
    title, items = MENU_PAGES[page]
    e = discord.Embed(title=f"Menu Chị Cá — {title}", color=EMBED_COLOR)
    if bot.user:
        e.set_author(name="Chị Cá", icon_url=bot.user.display_avatar.url)
    e.set_thumbnail(url=LEVELUP_GIF)
    for name, val in items:
        e.add_field(name=name, value=val, inline=True)
    e.set_footer(text=f"Trang {page + 1}/{len(MENU_PAGES)} • Gõ \"chị cá menu\" để xem lại nhé!")
    return e


class MenuView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot
        self.page = 0

    async def _show(self, interaction):
        self.page_indicator.label = f"{self.page + 1}/{len(MENU_PAGES)}"
        await interaction.response.edit_message(
            embed=_menu_embed(self.bot, self.page), view=self
        )

    @discord.ui.button(label="◀️", style=discord.ButtonStyle.secondary)
    async def prev(self, interaction, button):
        self.page = (self.page - 1) % len(MENU_PAGES)
        await self._show(interaction)

    @discord.ui.button(label="1/1", style=discord.ButtonStyle.secondary, disabled=True)
    async def page_indicator(self, interaction, button):
        pass

    @discord.ui.button(label="▶️", style=discord.ButtonStyle.secondary)
    async def next(self, interaction, button):
        self.page = (self.page + 1) % len(MENU_PAGES)
        await self._show(interaction)


async def handle_menu(message, bot):
    await message.channel.send(
        embed=_menu_embed(bot, 0), view=MenuView(bot), reference=message, mention_author=False
    )


def _member_list_embed(message, bot):
    guild = message.guild
    members = guild.members
    online = [m for m in members if m.status != discord.Status.offline]
    total, online_count = len(members), len(online)
    e = discord.Embed(title="👥 Thành viên online", color=EMBED_COLOR)
    if bot.user:
        e.set_author(name="Chị Cá 🐟", icon_url=bot.user.display_avatar.url)
    if guild.icon:
        e.set_thumbnail(url=guild.icon.url)
    e.description = f"**{online_count}/{total}** thành viên đang online"
    for m in online[:20]:
        role = m.top_role.name if m.top_role.name != "@everyone" else ""
        status = "🟢" if m.status == discord.Status.online else "🟡"
        e.add_field(name=f"{status} {m.display_name}", value=role or "—", inline=True)
    footer = (f"...và {online_count - 20} người nữa • " if online_count > 20 else "") + guild.name
    e.set_footer(text=footer, icon_url=guild.icon.url if guild.icon else discord.Embed.Empty)
    return e


async def handle_member_list(message, bot):
    await message.channel.send(
        embed=_member_list_embed(message, bot), reference=message, mention_author=False
    )


async def handle_invite(message, bot):
    try:
        invite = await message.channel.create_invite(
            max_age=604800,
            max_uses=0,
            unique=True,
            reason="Tạo lời mời bởi Chị Cá",
        )
        await message.channel.send(
            f"🔗 Lời mời vào server: {invite.url}\n(Link hiệu lực 7 ngày)",
            reference=message, mention_author=False,
        )
    except Exception as e:
        print(f"LỖI CREATE INVITE: {type(e).__name__}: {e}", flush=True)
        await message.channel.send(
            "Chị không tạo được lời mời 😭 (bot thiếu quyền **Create Instant Invite** "
            "hoặc kênh không cho phép tạo invite).",
            reference=message, mention_author=False,
        )


async def handle_poll(message, bot) -> bool:
    raw = message.content
    raw = re.sub(r"(?i)^(chị\s*cá|chica)\s*", "", raw).strip()
    raw = re.sub(r"(?i)^(poll|vote|bầu|bỏ\s*phiếu)\s*", "", raw).strip()
    segments = [s.strip() for s in re.split(r"\||;", raw) if s.strip()]

    if len(segments) < 3:
        await message.channel.send(
            "Em viết chưa đúng format rồi. "
            "Gõ: `vote Câu hỏi? | chọn 1 | chọn 2` (phân tách bằng `|`) 🐟",
            reference=message, mention_author=False,
        )
        return True

    question = segments[0]
    options = segments[1:]
    if len(options) > 10:
        options = options[:10]

    sender = message.author.display_name or message.author.name
    e = discord.Embed(
        title=f"📊 {question}",
        description="\n".join(
            f"{NUMBER_EMOJIS[i]} {opt}" for i, opt in enumerate(options)
        ),
        color=EMBED_COLOR,
    )
    if bot.user:
        e.set_author(name="Chị Cá 🐟", icon_url=bot.user.display_avatar.url)
    e.set_footer(text=f"Bỏ phiếu bằng cách react số tương ứng! • {sender} tạo")
    poll_msg = await message.channel.send(embed=e)
    for i in range(len(options)):
        await poll_msg.add_reaction(NUMBER_EMOJIS[i])
    return True
