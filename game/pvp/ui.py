import asyncio

import discord

from config import (
    PVP_TEAM_SIZE,
    PVP_ACCEPT_TIMEOUT,
    PVP_TURN_TIMEOUT,
    PVP_ENERGY_MAX,
    PVP_SP_MAX,
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
)
from .engine import BattleSession
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


# ====================== BATTLE (team rotation + SP) ======================
class ControlPanelView(discord.ui.View):
    def __init__(self, battle: BattleSession):
        super().__init__(timeout=PVP_TURN_TIMEOUT)
        self.battle = battle
        team = battle._active_team()
        pending = battle.pending_actor(team)
        chars = [pending] if pending else battle.available_chars(team)
        enemies = [f for f in battle._enemy_of(team[0]) if f.alive] if team else []
        self._add_selects(chars, enemies)

        sp = battle.sp_a if battle.active_team == "A" else battle.sp_b
        self.btn_normal = discord.ui.Button(label="⚔️ Đánh thường", style=discord.ButtonStyle.secondary)
        self.btn_skill = discord.ui.Button(label="🔥 Skill", style=discord.ButtonStyle.primary, disabled=(sp <= 0))
        self.btn_ult = discord.ui.Button(label="✨ Ultimate", style=discord.ButtonStyle.danger)
        self.btn_normal.callback = lambda i: self._act(i, "normal")
        self.btn_skill.callback = lambda i: self._act(i, "skill")
        self.btn_ult.callback = lambda i: self._act(i, "ultimate")
        self.add_item(self.btn_normal)
        self.add_item(self.btn_skill)
        self.add_item(self.btn_ult)
        if pending is not None:
            self.btn_skip_pending = discord.ui.Button(label="⏭️ Bỏ đánh thường", style=discord.ButtonStyle.secondary)
            self.btn_skip_pending.callback = self._skip_pending
            self.add_item(self.btn_skip_pending)

    def _add_selects(self, chars: list, enemies: list):
        if chars:
            self.char_select = discord.ui.Select(
                placeholder="① Chọn thẻ hành động",
                min_values=1, max_values=1,
                options=[discord.SelectOption(
                    label=f.name, value=f.key,
                    description=f"{ROLE_LABEL[f.role]} • {f.element}",
                    emoji=ELEMENT_EMOJI.get(f.element, "❔"),
                ) for f in chars],
            )
            self.char_select.callback = self._noop
            self.add_item(self.char_select)
        if enemies:
            self.target_select = discord.ui.Select(
                placeholder="② Chọn mục tiêu địch",
                min_values=1, max_values=1,
                options=[discord.SelectOption(
                    label=e.name, value=e.key,
                    description=f"{ROLE_LABEL[e.role]} • {e.element}",
                    emoji=ELEMENT_EMOJI.get(e.element, "❔"),
                ) for e in enemies],
            )
            self.target_select.callback = self._noop
            self.add_item(self.target_select)

    async def _noop(self, interaction: discord.Interaction):
        await interaction.response.defer()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.battle._owner_active().id

    async def _skip_pending(self, interaction: discord.Interaction):
        battle = self.battle
        if battle.done:
            return
        team = battle._active_team()
        actor = battle.pending_actor(team)
        if actor is not None:
            battle.skip_pending(actor)
        for it in self.children:
            it.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()
        await _after_action(battle)

    async def _act(self, interaction: discord.Interaction, action: str):
        battle = self.battle
        char_select = getattr(self, "char_select", None)
        target_select = getattr(self, "target_select", None)
        char_key = char_select.values[0] if (char_select and char_select.values) else None
        if char_key is None:
            await interaction.response.send_message("Hãy chọn ① thẻ hành động!", ephemeral=True)
            return
        actor = next((f for f in battle._active_team() if f.key == char_key), None)
        if actor is None or not actor.alive or actor.turn_done or actor.stunned:
            await interaction.response.send_message("Thẻ không hợp lệ!", ephemeral=True)
            return

        eff = actor.skill if action == "skill" else (actor.ultimate if action == "ultimate" else None)
        needs_target = action == "normal" or (eff is not None and eff["type"] in ("ST_DMG", "STUN", "HEAL_ST_DMG"))
        target = None
        if needs_target:
            tkey = target_select.values[0] if (target_select and target_select.values) else None
            if tkey is None:
                await interaction.response.send_message("Hãy chọn ② mục tiêu địch!", ephemeral=True)
                return
            target = next((e for e in battle._enemy_of(actor) if e.key == tkey and e.alive), None)
            if target is None:
                await interaction.response.send_message("Mục tiêu không hợp lệ!", ephemeral=True)
                return

        sp = battle._sp_of(actor)
        if action == "skill" and sp <= 0:
            await interaction.response.send_message("Hết Skill Point! 🔋", ephemeral=True)
            return
        if action == "ultimate" and actor.energy < PVP_ENERGY_MAX:
            await interaction.response.send_message("Chưa đủ energy Ultimate! ⚡", ephemeral=True)
            return
        if not battle.apply_action(actor, action, target):
            await interaction.response.send_message("Không thể thực hiện hành động này!", ephemeral=True)
            return

        for it in self.children:
            it.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()
        await _after_action(battle)

    async def on_timeout(self):
        if self.battle.done:
            return
        team = self.battle._active_team()
        pending = self.battle.pending_actor(team)
        if pending is not None:
            actor = pending
            enemies = [e for e in self.battle._enemy_of(actor) if e.alive]
            target = enemies[0] if enemies else None
            if not self.battle.apply_action(actor, "normal", target):
                self.battle.skip_pending(actor)
        else:
            chars = self.battle.available_chars(team)
            if not chars:
                await _after_action(self.battle)
                return
            actor = chars[0]
            enemies = [e for e in self.battle._enemy_of(actor) if e.alive]
            target = enemies[0] if enemies else None
            self.battle.apply_action(actor, "normal", target)
        for it in self.children:
            it.disabled = True
        await _after_action(self.battle)


async def _resolve(session: PVPSession, interaction: discord.Interaction):
    if session.done or not session.a_cards or not session.b_cards:
        return
    pending_challenges.discard(_challenge_key(session.challenger.id, session.target.id))
    session.done = True

    battle = BattleSession(
        session.a_cards, session.b_cards,
        session.challenger, session.target,
        interaction.channel, interaction.client,
    )
    anim = discord.Embed(title="⚔️ Bắt đầu!", color=PVP_COLOR)
    anim.set_image(url=PVP_BATTLE_ANIM_GIF)
    anim_msg = await interaction.followup.send(embed=anim)
    await asyncio.sleep(2.5)
    try:
        await anim_msg.delete()
    except Exception:
        pass

    battle.message = await interaction.followup.send(
        embed=discord.Embed(title="⚔️ Đang vào trận...", color=PVP_COLOR)
    )
    await _post_panel(battle)


async def _post_panel(battle: BattleSession):
    team = battle._active_team()
    if not battle.available_chars(team):
        for f in team:
            f.stunned = False
        if not battle.available_chars(team):
            w = battle.check_winner()
            await _finish_battle(battle, w if w is not False else None)
            return
    embed = _battle_embed(battle)
    try:
        await battle.message.edit(embed=embed, view=ControlPanelView(battle))
    except Exception as e:
        print("LỖI POST_PANEL:", e, flush=True)


async def _after_action(battle: BattleSession):
    w = battle.check_winner()
    if w is not False:
        await _finish_battle(battle, w)
        return
    active = battle._active_team()
    if not battle.available_chars(active):
        battle.end_rotation()
    await _post_panel(battle)


async def _finish_battle(battle: BattleSession, winner):
    battle.done = True
    ra_row = await get_pvp_rating(battle.a_user.id)
    rb_row = await get_pvp_rating(battle.b_user.id)
    ra = ra_row["rating"]
    rb = rb_row["rating"]
    if winner == "A":
        na, nb = compute_elo(ra, rb)
        win_user, lose_user = battle.a_user, battle.b_user
        draw = False
    elif winner == "B":
        nb, na = compute_elo(rb, ra)
        win_user, lose_user = battle.b_user, battle.a_user
        draw = False
    else:
        na, nb = compute_elo_draw(ra, rb)
        win_user, lose_user = None, None
        draw = True
    await update_pvp_result(battle.a_user.id, battle.b_user.id, na, nb, draw)

    result = {
        "winner": winner,
        "log": battle.log,
        "team_a": battle.team_a,
        "team_b": battle.team_b,
    }
    embed = _result_embed(battle, result, ra, rb, na, nb, win_user, lose_user, draw)
    try:
        await battle.message.edit(embed=embed, view=None)
    except Exception as e:
        print("LỖI FINISH_BATTLE:", e, flush=True)


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


def _team_battle_lines(team, battle):
    lines = []
    for f in team:
        mark = "💀" if not f.alive else ("✅" if f.turn_done else ("⭐" if f.stunned else "❤️"))
        if not f.alive:
            lines.append(f"💀 {f.name}")
            continue
        pending_txt = " • ↻ còn 1 hành động" if f.pending else ""
        lines.append(
            f"{mark} {ELEMENT_EMOJI.get(f.element,'❔')} **{f.name}** [{ROLE_LABEL[f.role]}]\n"
            f"{_bar(max(0,f.hp), f.max_hp)} {max(0,f.hp)}/{f.max_hp}\n"
            f"⚡{f.energy}/{PVP_ENERGY_MAX}{' 🛡️' if f.shield > 0 else ''}{pending_txt}"
        )
    return "\n".join(lines)


def _battle_embed(battle: BattleSession):
    e = discord.Embed(title=f"⚔️ PvP — Lượt {battle._owner_active().display_name}", color=PVP_COLOR)
    e.set_author(name="Chị Cá 🐟 PvP")
    sp = battle.sp_a if battle.active_team == "A" else battle.sp_b
    e.add_field(
        name=f"🔵 {battle.a_user.display_name}",
        value=_team_battle_lines(battle.team_a, battle),
        inline=True,
    )
    e.add_field(
        name=f"🔴 {battle.b_user.display_name}",
        value=_team_battle_lines(battle.team_b, battle),
        inline=True,
    )
    e.add_field(
        name="🎯 Đến lượt",
        value=f"{battle._owner_active().mention} — 🔋 SP {sp}/{PVP_SP_MAX}\n"
              f"① Chọn thẻ · ② Chọn mục tiêu · bấm hành động",
        inline=False,
    )
    log = battle.log[-10:]
    e.add_field(
        name="📜 Diễn biến",
        value="```" + "\n".join(log) + "```" if log else "—",
        inline=False,
    )
    return e


def _result_embed(battle, result, ra, rb, na, nb, win_user, lose_user, draw):
    if draw:
        title = "🤝 HÒA!"
        color = 0x95A5A6
    else:
        title = f"🏆 {win_user.display_name} THẮNG!"
        color = ROLE_COLOR.get("DPS", PVP_COLOR)
    e = discord.Embed(title=title, color=color)
    e.set_author(name="Chị Cá 🐟 PvP")

    ta = result["team_a"]
    tb = result["team_b"]

    e.add_field(
        name=f"🔵 Đội {battle.a_user.display_name} (Rank {ra}→{na})",
        value=_team_result_lines(ta),
        inline=True,
    )
    e.add_field(
        name=f"🔴 Đội {battle.b_user.display_name} (Rank {rb}→{nb})",
        value=_team_result_lines(tb),
        inline=True,
    )

    log = result["log"]
    shown = (log[:10] + ["...", "..."] + log[-4:]) if len(log) > 16 else log
    e.add_field(
        name="📜 Diễn biến",
        value="```" + "\n".join(shown) + "```" if shown else "—",
        inline=False,
    )

    if not draw:
        delta_a = na - ra
        e.set_footer(
            text=f"{win_user.display_name} {('+' if delta_a>=0 else '')}{delta_a} rank · "
                 f"{lose_user.display_name} {nb-rb} rank"
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
    e.set_footer(text="Mỗi lượt: chọn thẻ + mục tiêu + hành động (Đánh thường/Skill/Ultimate) · SP chung team")
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
                user = bot.get_user(uid) or (message.guild.get_member(uid) if message.guild else None)
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
    rating = row["rating"]
    wins = row["wins"]
    losses = row["losses"]
    e = discord.Embed(title=f"⭐ Hạng PvP của {target.display_name}", color=PVP_COLOR)
    e.set_author(name="Chị Cá 🐟 PvP")
    e.set_thumbnail(url=target.display_avatar.url)
    e.add_field(name="Rank", value=f"**{rating}**", inline=True)
    e.add_field(name="Thắng", value=f"{wins}", inline=True)
    e.add_field(name="Thua", value=f"{losses}", inline=True)
    e.set_footer(text="Thắng +rank, thua -rank (ELO K=32)")
    await message.channel.send(embed=e, reference=message)
