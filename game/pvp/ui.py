import asyncio
import random

import discord

from config import (
    PVP_TEAM_SIZE,
    PVP_ACCEPT_TIMEOUT,
    PVP_START_RATING,
    PVP_BATTLE_ANIM_GIF,
)
from db import (
    get_collection,
    get_pvp_rating,
    get_pvp_top,
    update_pvp_result,
)
from .cards import (
    get_card,
    ROLE_LABEL,
    ROLE_COLOR,
    ELEMENT_EMOJI,
    RARITY_BY_KEY,
)
from .engine import resolve_battle
from .ranks import compute_elo, compute_elo_draw, START_RATING

PVP_COLOR = 0x9B59B6
pending_challenges = set()


class PVPSession:
    def __init__(self, challenger, target, channel):
        self.challenger = challenger
        self.target = target
        self.channel = channel
        self.a_cards = None
        self.b_cards = None
        self.done = False


def _bar(done, total, size=10):
    filled = round(done / total * size) if total else 0
    return "▰" * filled + "▱" * (size - filled)


def _challenge_key(a, b):
    return frozenset((a, b))


# ====================== CHALLENGE ======================
class ChallengeView(discord.ui.View):
    def __init__(self, session: PVPSession):
        super().__init__(timeout=PVP_ACCEPT_TIMEOUT)
        self.session = session

    async def on_timeout(self):
        pending_challenges.discard(_challenge_key(self.session.challenger.id, self.session.target.id))
        for item in self.children:
            item.disabled = True

    @discord.ui.button(label="⚔️ Chấp nhận", style=discord.ButtonStyle.primary)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.target.id:
            await interaction.response.send_message(
                "Chỉ người được thách đấu mới được chấp nhận!", ephemeral=True
            )
            return
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(
            content=f"✅ {self.session.target.mention} đã chấp nhận! Đang lập đội...",
            view=self,
        )
        await _begin_selection(interaction, self.session, "A")

    @discord.ui.button(label="❌ Từ chối", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.target.id:
            await interaction.response.send_message(
                "Chỉ người được thách đấu mới được từ chối!", ephemeral=True
            )
            return
        pending_challenges.discard(_challenge_key(self.session.challenger.id, self.session.target.id))
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(
            content=f"❌ {self.session.target.mention} đã từ chối thách đấu.",
            view=self,
        )
        self.session.done = True


# ====================== TEAM SELECT ======================
class TeamSelectView(discord.ui.View):
    def __init__(self, session: PVPSession, side: str, options, max_pick: int):
        super().__init__(timeout=120)
        self.session = session
        self.side = side
        select = discord.ui.Select(
            placeholder="Chọn thẻ lập đội...",
            min_values=max_pick,
            max_values=max_pick,
            options=options,
        )
        select.callback = self._on_select
        self.add_item(select)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

    async def _on_select(self, interaction: discord.Interaction):
        expected = self.session.challenger.id if self.side == "A" else self.session.target.id
        if interaction.user.id != expected:
            await interaction.response.send_message(
                "Không phải lượt chọn của em!", ephemeral=True
            )
            return
        vals = interaction.data.get("values", [])
        chosen = [get_card(v) for v in vals]
        if self.side == "A":
            self.session.a_cards = chosen
        else:
            self.session.b_cards = chosen
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(
            content=f"✅ {interaction.user.mention} đã chốt đội!",
            embed=_team_preview_embed(interaction.user, chosen),
        )
        if self.side == "A":
            await _begin_selection(interaction, self.session, "B")
        else:
            await _resolve(self.session, interaction)


async def _begin_selection(interaction, session: PVPSession, side: str):
    user = session.challenger if side == "A" else session.target
    rows = await get_collection(user.id)
    owned_keys = [r["char_key"] for r in rows]
    cards = [get_card(k) for k in owned_keys if get_card(k)]
    if not cards:
        await interaction.followup.send(
            f"{user.mention} chưa có thẻ nào để đánh! (quay gacha trước đi 🎴)",
            ephemeral=True,
        )
        pending_challenges.discard(_challenge_key(session.challenger.id, session.target.id))
        return
    max_pick = min(PVP_TEAM_SIZE, len(cards))
    options = [
        discord.SelectOption(
            label=c["name"],
            value=c["key"],
            description=f"{ROLE_LABEL[c['role']]} • {c['element']}",
            emoji=ELEMENT_EMOJI.get(c["element"], "❔"),
        )
        for c in cards
    ]
    view = TeamSelectView(session, side, options, max_pick)
    await interaction.followup.send(
        f"{user.mention} chọn **{max_pick}** thẻ để lập đội:", view=view
    )


# ====================== RESOLVE ======================
async def _resolve(session: PVPSession, interaction: discord.Interaction):
    if session.done or not session.a_cards or not session.b_cards:
        return
    pending_challenges.discard(_challenge_key(session.challenger.id, session.target.id))
    session.done = True

    result = resolve_battle(session.a_cards, session.b_cards)

    ra_row = await get_pvp_rating(session.challenger.id)
    rb_row = await get_pvp_rating(session.target.id)
    ra = ra_row["rating"] if ra_row else START_RATING
    rb = rb_row["rating"] if rb_row else START_RATING

    if result["winner"] == "A":
        na, nb = compute_elo(ra, rb)
        win_user, lose_user = session.challenger, session.target
        draw = False
    elif result["winner"] == "B":
        nb, na = compute_elo(rb, ra)
        win_user, lose_user = session.target, session.challenger
        draw = False
    else:
        na, nb = compute_elo_draw(ra, rb)
        win_user, lose_user = None, None
        draw = True

    await update_pvp_result(session.challenger.id, session.target.id, na, nb, draw)

    anim = discord.Embed(title="⚔️ Đang chiến đấu...", color=PVP_COLOR)
    anim.set_image(url=PVP_BATTLE_ANIM_GIF)
    anim_msg = await interaction.followup.send(embed=anim)
    await asyncio.sleep(3.0)
    try:
        await anim_msg.delete()
    except Exception:
        pass

    await interaction.followup.send(
        embed=_result_embed(session, result, ra, rb, na, nb, win_user, lose_user, draw)
    )


# ====================== EMBEDS ======================
def _team_preview_embed(user, cards):
    e = discord.Embed(title=f"🎴 Đội của {user.display_name}", color=PVP_COLOR)
    if cards:
        e.set_thumbnail(url=cards[0]["url"])
    for c in cards:
        e.add_field(
            name=f"{ELEMENT_EMOJI.get(c['element'],'❔')} {c['name']} "
                  f"[{ROLE_LABEL[c['role']]}]",
            value=f"⚔️ ATK {c['atk']} · ❤️ HP {c['hp']} · 💨 SPD {c['spd']}\n"
                  f"💥 CRIT {int(c['crit_rate']*100)}% / x{c['crit_dmg']} · "
                  f"🔮 {c['skill']['name']}",
            inline=True,
        )
    return e


def _result_embed(session, result, ra, rb, na, nb, win_user, lose_user, draw):
    if draw:
        title = "🤝 HÒA!"
        color = 0x95A5A6
    else:
        title = f"🏆 {win_user.display_name} THẮNG!"
        color = ROLE_COLOR.get("DPS", PVP_COLOR)
    e = discord.Embed(title=title, color=color)
    e.set_author(name="Chị Cá 🐟 PvP")

    a_name = session.challenger.display_name
    b_name = session.target.display_name

    ta = result["team_a"]
    tb = result["team_b"]

    e.add_field(
        name=f"🔵 Đội {a_name} (Rank {ra}→{na})",
        value=_team_result_lines(ta),
        inline=True,
    )
    e.add_field(
        name=f"🔴 Đội {b_name} (Rank {rb}→{nb})",
        value=_team_result_lines(tb),
        inline=True,
    )

    log = result["log"]
    if len(log) > 18:
        shown = log[:12] + ["...", "..."] + log[-4:]
    else:
        shown = log
    e.add_field(
        name="📜 Diễn biến",
        value="```" + "\n".join(shown) + "```" if shown else "—",
        inline=False,
    )

    if not draw:
        delta_a = na - ra
        delta_b = nb - rb
        e.set_footer(
            text=f"{win_user.display_name} +{delta_a if delta_a>0 else delta_a} rank · "
                 f"{lose_user.display_name} {delta_b} rank"
        )
    else:
        e.set_footer(text="Hòa, không đổi rank")
    return e


def _team_result_lines(team):
    lines = []
    for f in team:
        status = "💀" if not f.alive else "❤️"
        lines.append(
            f"{status} {ELEMENT_EMOJI.get(f.element,'❔')} **{f.name}** "
            f"[{ROLE_LABEL[f.role]}]\n"
            f"{_bar(max(0,f.hp), f.max_hp)} {max(0,f.hp)}/{f.max_hp}"
        )
    return "\n".join(lines)


# ====================== ENTRY POINTS ======================
async def start_pvp_challenge(message, bot):
    target = message.mentions[0] if message.mentions else None
    if target is None:
        await message.channel.send(
            "Em cần mention người muốn thách đấu: `chị cá pvp @người_chơi` 🐟",
            reference=message,
        )
        return
    if target.bot:
        await message.channel.send("Không thể thách đấu bot! 🐟", reference=message)
        return
    if target.id == message.author.id:
        await message.channel.send("Em không thể tự thách đấu chính mình 😅", reference=message)
        return
    key = _challenge_key(message.author.id, target.id)
    if key in pending_challenges:
        await message.channel.send("Đã có một thách đấu đang chờ giữa hai em! ⏳", reference=message)
        return

    rows_a = await get_collection(message.author.id)
    rows_b = await get_collection(target.id)
    if not rows_a:
        await message.channel.send(
            f"{message.author.mention} chưa có thẻ nào (quay gacha trước đã) 🎴",
            reference=message,
        )
        return
    if not rows_b:
        await message.channel.send(
            f"{target.mention} chưa có thẻ nào để đấu 🎴", reference=message
        )
        return

    pending_challenges.add(key)
    session = PVPSession(message.author, target, message.channel)

    e = discord.Embed(
        title="⚔️ THÁCH ĐẤU PvP",
        description=f"{message.author.mention} thách đấu {target.mention}!\n"
        f"{target.mention} có 60 giây để chấp nhận.",
        color=PVP_COLOR,
    )
    e.set_author(name="Chị Cá 🐟 PvP")
    e.set_thumbnail(url=PVP_BATTLE_ANIM_GIF)
    e.set_footer(text="Chọn 3 thẻ tự do · DPS gây dame · TANK giáp team · SUP buff/heal")
    await message.channel.send(embed=e, view=ChallengeView(session), reference=message)


async def handle_pvp_rank(message, bot):
    cl = message.content.lower()
    if any(k in cl for k in ("top", "xếp hạng", "leaderboard", "bảng")):
        rows = await get_pvp_top(10)
        e = discord.Embed(title="🏆 Top 10 PvP Chị Cá", color=PVP_COLOR)
        e.set_author(name="Chị Cá 🐟 PvP")
        if not rows:
            e.description = "Chưa có ai thi đấu. `chị cá pvp @ai` để mở thứ hạng!"
        else:
            medals = {1: "🥇", 2: "🥈", 3: "🥉"}
            for i, r in enumerate(rows, 1):
                uid = r["user_id"]
                user = bot.get_user(uid) or message.guild.get_member(uid) if message.guild else None
                name = user.display_name if user else f"user {uid}"
                e.add_field(
                    name=f"{medals.get(i, f'#{i}')} {name}",
                    value=f"⭐ Rank **{r['rating']}** · {r['wins']}W/{r['losses']}L",
                    inline=False,
                )
        await message.channel.send(embed=e, reference=message)
        return

    target = message.mentions[0] if message.mentions else message.author
    row = await get_pvp_rating(target.id)
    rating = row["rating"] if row else START_RATING
    wins = row["wins"] if row else 0
    losses = row["losses"] if row else 0
    e = discord.Embed(title=f"⭐ Hạng PvP của {target.display_name}", color=PVP_COLOR)
    e.set_author(name="Chị Cá 🐟 PvP")
    e.set_thumbnail(url=target.display_avatar.url)
    e.add_field(name="Rank", value=f"**{rating}**", inline=True)
    e.add_field(name="Thắng", value=f"{wins}", inline=True)
    e.add_field(name="Thua", value=f"{losses}", inline=True)
    e.set_footer(text="Thắng +rank, thua -rank (ELO K=32)")
    await message.channel.send(embed=e, reference=message)
