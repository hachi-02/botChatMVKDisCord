# =============================================
# features/server_tools.py
# Các công cụ server: menu, danh sách thành viên, vote (poll), link mời.
# Tách từ bot.py. Nhận `bot` qua tham số, không import bot (tránh circular import).
# =============================================

import re
import random

import discord

from config import HUG_GIFS
from points import EMBED_COLOR

# Bộ emoji số 1-10 dùng để gán cho các lựa chọn trong poll
NUMBER_EMOJIS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

# Nội dung menu điều hướng gồm nhiều trang. Mỗi trang = (tiêu đề, [(tên, mô tả), ...])
MENU_PAGES = [
    (
        "💬 Trò chuyện & Thông tin",
        [
            ("💬 Nói chuyện", "Gọi `chị cá` hoặc tag chị"),
            ("🔍 Tìm web", "`chica search <câu hỏi>`"),
            ("👥 Thành viên online", "`chica member`"),
            ("🔎 Tóm tắt", "`chica summary 1 tiếng` / `chica summary 30 tin`"),
        ],
    ),
    (
        "🛠️ Công cụ Server",
        [
            ("📊 Vote", "`chica vote Câu hỏi? | chọn 1 | chọn 2`"),
            ("⏰ Nhắc", "`chica remind 7h học bài`"),
            ("📅 Điểm danh", "`chica daily` (mỗi ngày +10💠 +500🪙)"),
            ("📅 Sự kiện", "`chica make event Tên | thời gian | mô tả | địa điểm`"),
            ("🔗 Lời mời", "`chica link`"),
            ("🎧 Kênh thoại", "`chica voice in` / `chica voice out`"),
            ("🤗 Ôm", "`chica hug @bạn` (tặng cái ôm kèm GIF)"),
        ],
    ),
    (
        "🎮 Trò chơi & Điểm",
        [
            ("💠 Tài sản", "`chica bag` (xem nguyên thạch / mora / cấp)"),
            ("🎴 Gacha", "`chica gacha` / `chica gacha 1` / `chica gacha 5` (50❖ / 250❖)"),
            ("🗃️ Kho thẻ", "`chica inventory` (xem các thẻ đã có)"),
            ("⚔️ PvP", "`chica pvp @người_chơi` (3v3 turn-based, ELO)"),
            ("🏆 Xếp hạng PvP", "`chica pvp point` / `chica pvp top`"),
            ("ℹ️ Thông tin thẻ", "`chica info + tên` (vd: `chica info skirk` — xem thẻ đã sở hữu)"),
        ],
    ),
]


# Tạo nội dung text của menu trang `page` (nằm trong TextDisplay của Container).
def _menu_text(page=0):
    title, items = MENU_PAGES[page]
    lines = [f"# 🐟 Menu Chị Cá", "", f"## {title}", ""]
    for name, val in items:
        lines.append(f"**{name}** — {val}")
    lines.append("")
    lines.append(f"_Trang {page + 1}/{len(MENU_PAGES)} • Gõ \"chica menu\" để xem lại!_")
    return "\n".join(lines)


# Giao diện menu Components V2: 2 nút ◀️/▶️ (và nhãn trang) nằm trong cùng 1 Container
# với phần tiêu đề Menu Chị Cá (tương tự GachaView).
class MenuView(discord.ui.LayoutView):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot
        self.page = 0           # Trang hiện tại
        self.message = None

        # Nút lùi / nhãn chỉ trang / nút tới
        self.btn_prev = discord.ui.Button(
            label="◀️",
            style=discord.ButtonStyle.secondary,
        )
        self.btn_prev.callback = self._prev
        self.btn_indicator = discord.ui.Button(
            label=f"1/{len(MENU_PAGES)}",
            style=discord.ButtonStyle.secondary,
            disabled=True,
        )
        self.btn_next = discord.ui.Button(
            label="▶️",
            style=discord.ButtonStyle.secondary,
        )
        self.btn_next.callback = self._next

        # Hàng chứa 3 nút, đặt trong container
        self.button_row = discord.ui.ActionRow()
        self.button_row.add_item(self.btn_prev)
        self.button_row.add_item(self.btn_indicator)
        self.button_row.add_item(self.btn_next)

        # Text hiển thị nội dung trang (nằm trong container)
        self.menu_text = discord.ui.TextDisplay(
            content=_menu_text(self.page)
        )

        # Container = khung bao gồm text + hàng nút
        self.container = discord.ui.Container(
            self.menu_text,
            self.button_row,
            accent_color=EMBED_COLOR,
        )
        self.add_item(self.container)

    # Cập nhật nội dung text + nhãn trang, rồi chỉnh lại view trong tin nhắn
    async def _show(self, interaction):
        self.menu_text.content = _menu_text(self.page)
        self.btn_indicator.label = f"{self.page + 1}/{len(MENU_PAGES)}"
        await interaction.response.edit_message(view=self)

    # Nút lùi về trang trước (vòng lại trang cuối nếu đứng ở trang đầu)
    async def _prev(self, interaction):
        self.page = (self.page - 1) % len(MENU_PAGES)
        await self._show(interaction)

    # Nút qua trang kế tiếp (vòng lại trang đầu nếu ở trang cuối)
    async def _next(self, interaction):
        self.page = (self.page + 1) % len(MENU_PAGES)
        await self._show(interaction)


# Gửi menu (container có text + 2 nút điều hướng trong cùng khung) vào kênh.
async def handle_menu(message, bot):
    view = MenuView(bot)
    g_msg = await message.channel.send(
        view=view, reference=message, mention_author=False
    )
    view.message = g_msg


# Tạo embed danh sách thành viên đang online (hiện tối đa 20 người + vai trò).
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
    for m in online[:20]:   # Chỉ liệt kê 20 người đầu để tránh embed quá dài
        role = m.top_role.name if m.top_role.name != "@everyone" else ""
        status = "🟢" if m.status == discord.Status.online else "🟡"
        e.add_field(name=f"{status} {m.display_name}", value=role or "—", inline=True)
    footer = (f"...và {online_count - 20} người nữa • " if online_count > 20 else "") + guild.name
    e.set_footer(text=footer, icon_url=guild.icon.url if guild.icon else discord.Embed.Empty)
    return e


# Gửi danh sách thành viên online vào kênh.
async def handle_member_list(message, bot):
    await message.channel.send(
        embed=_member_list_embed(message, bot), reference=message, mention_author=False
    )


# Tạo link mời trực tiếp trong kênh hiện tại (hiệu lực 7 ngày, không giới hạn lượt).
async def handle_invite(message, bot):
    try:
        invite = await message.channel.create_invite(
            max_age=604800,   # 7 ngày (604800 giây)
            max_uses=0,       # 0 = không giới hạn số lần dùng
            unique=True,
            reason="Tạo lời mời bởi Chị Cá",
        )
        await message.channel.send(
            f"🔗 Lời mời vào server: {invite.url}\n(Link hiệu lực 7 ngày)",
            reference=message, mention_author=False,
        )
    except Exception as e:
        # Thiếu quyền Create Instant Invite thường là nguyên nhân
        print(f"LỖI CREATE INVITE: {type(e).__name__}: {e}", flush=True)
        await message.channel.send(
            "Chị không tạo được lời mời 😭 (bot thiếu quyền **Create Instant Invite** "
            "hoặc kênh không cho phép tạo invite).",
            reference=message, mention_author=False,
        )


# Xử lý lệnh "ôm" (vd: `chica hug @bạn`). Gửi 1 message: text + GIF ngẫu nhiên.
# Nếu không có @người nhận thì tự ôm bot.
async def handle_hug(message, bot) -> bool:
    target = message.mentions[0] if message.mentions else bot.user
    gif = random.choice(HUG_GIFS)
    await message.channel.send(
        f"{message.author.mention} tặng cái ôm {target.mention} 🐟\n{gif}",
        reference=message,
        mention_author=False,
    )
    return True


# Xử lý lệnh vote/poll (vd: `chị cá vote Đi ăn gì? | Phở | Bún`).
# Tách câu hỏi + các lựa chọn bằng "|" hoặc ";", gắn emoji số để bỏ phiếu.
async def handle_poll(message, bot) -> bool:
    raw = message.content
    # Bỏ tiền tố "chị cá/chica" và từ khóa "poll/vote/bầu/bỏ phiếu"
    raw = re.sub(r"(?i)^(chị\s*cá|chica)\s*", "", raw).strip()
    raw = re.sub(r"(?i)^(vote|poll|bầu|bỏ\s*phiếu)\s*", "", raw).strip()
    # Tách thành: câu hỏi + các lựa chọn
    segments = [s.strip() for s in re.split(r"\||;", raw) if s.strip()]

    # Cần tối thiểu: câu hỏi + 2 lựa chọn (tức >= 3 phần)
    if len(segments) < 3:
        await message.channel.send(
            "Em viết chưa đúng format rồi. "
            "Gõ: `chica vote Câu hỏi? | chọn 1 | chọn 2` (phân tách bằng `|`) 🐟",
            reference=message, mention_author=False,
        )
        return True

    question = segments[0]
    options = segments[1:]
    if len(options) > 10:   # Discord chỉ cho tối đa 10 emoji số
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
    # Tự động gắn emoji số cho từng lựa chọn để người dùng bấm vote
    for i in range(len(options)):
        await poll_msg.add_reaction(NUMBER_EMOJIS[i])
    return True
