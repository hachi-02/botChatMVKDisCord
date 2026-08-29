import asyncio
import random

import discord

from config import (
    PVP_TEAM_SIZE,
    PVP_ACCEPT_TIMEOUT,
    PVP_TURN_TIMEOUT,
    PVP_ENERGY_MAX,
    PVP_SP_MAX,
    PVP_START_RATING,
    PVP_BATTLE_ANIM_GIF,
    PVP_CHALLENGE_GIF,
    CHAR_MAX_LEVEL,
    LEVEL_COST_PER,
    LEVEL_HP_BONUS,
    LEVEL_ATK_BONUS,
    LEVEL_SPD_BONUS,
)
from db import (
    get_collection,
    get_pvp_rating,
    get_pvp_top,
    update_pvp_result,
    get_char_level,
    set_char_level,
    get_mora,
    spend_mora,
)
from .cards import (
    get_card,
    element_name,
    ROLE_LABEL,
    ROLE_COLOR,
    ELEMENT_EMOJI,
)
from .engine import BattleSession
from .ranks import compute_elo, compute_elo_draw, START_RATING
from .battle_image import prepare_battle_image, render_battle_image

PVP_COLOR = 0x9B59B6
pending_challenges = set()
active_players = set()


def is_in_pvp(user_id: int) -> bool:
    return user_id in active_players


class _EphemeralStore:
    def __init__(self):
        self._msgs = set()

    async def send(self, interaction, content, seconds=5):
        try:
            await interaction.response.send_message(content, ephemeral=True)
        except Exception:
            return None
        try:
            msg = await interaction.original_response()
        except Exception:
            return None
        if msg is not None:
            self._msgs.add(msg)
            asyncio.create_task(self._auto_delete(msg, seconds))
        return msg

    async def flush(self):
        for msg in list(self._msgs):
            try:
                await msg.delete()
            except Exception:
                pass
        self._msgs.clear()

    async def _auto_delete(self, msg, seconds):
        await asyncio.sleep(seconds)
        self._msgs.discard(msg)
        try:
            await msg.delete()
        except Exception:
            pass


_ephemerals = _EphemeralStore()


class PVPSession:
    def __init__(self, challenger, target, channel):
        self.challenger = challenger
        self.target = target
        self.channel = channel
        self.a_cards = None
        self.b_cards = None
        self.a_levels = {}
        self.b_levels = {}
        self.first_user = None
        self.second_user = None
        self.done = False
        self.cancelled = False
        self.select_msgs = []
        self.confirm_msgs = []
        self.announce_msgs = []

    def user_for_side(self, side: str):
        if side == "A":
            return self.first_user or self.challenger
        return self.second_user or self.target


def _bar(done, total, size=10):
    filled = round(done / total * size) if total else 0
    return "▰" * filled + "▱" * (size - filled)


def _signed(delta):
    return f"+{delta}" if delta >= 0 else str(delta)


def _challenge_key(a, b):
    return frozenset((a, b))


def _release_session(session):
    pending_challenges.discard(
        _challenge_key(session.challenger.id, session.target.id)
    )
    active_players.discard(session.challenger.id)
    active_players.discard(session.target.id)


async def _cancel_team_select(session):
    for m in session.select_msgs:
        try:
            await m.delete()
        except Exception:
            pass
    for m in session.announce_msgs:
        try:
            await m.delete()
        except Exception:
            pass
    await _ephemerals.flush()
    try:
        await session.channel.send(
            f"⏳ Hết giờ chọn đội, trận giữa "
            f"{session.challenger.mention} và {session.target.mention} đã hủy."
        )
    except Exception:
        pass


# ====================== CHALLENGE ======================
class ChallengeView(discord.ui.View):
    def __init__(self, session: PVPSession):
        super().__init__(timeout=PVP_ACCEPT_TIMEOUT)
        self.session = session
        self.message = None

    async def on_timeout(self):
        if self.session.cancelled or self.session.done:
            return
        self.session.cancelled = True
        _release_session(self.session)
        for item in self.children:
            item.disabled = True
        try:
            await self.message.edit(
                content="⏳ Hết giờ chờ phản hồi, thách đấu đã tự hủy.",
                view=self,
            )
        except Exception:
            pass

    @discord.ui.button(label="⚔️ Chấp nhận", style=discord.ButtonStyle.primary)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.target.id:
            await _ephemerals.send(
                interaction, "Chỉ người được thách đấu mới được chấp nhận!"
            )
            return
        if self.session.cancelled or interaction.user.id not in active_players \
                or self.session.challenger.id not in active_players:
            await interaction.response.send_message(
                "⏳ Thách đấu đã hết hạn/tự hủy rồi!", ephemeral=True
            )
            return
        for item in self.children:
            item.disabled = True
        first = random.choice([self.session.challenger, self.session.target])
        second = (
            self.session.target
            if first.id == self.session.challenger.id
            else self.session.challenger
        )
        self.session.first_user = first
        self.session.second_user = second
        await interaction.response.edit_message(
            content=f"✅ {self.session.target.mention} đã chấp nhận!",
            view=self,
        )
        self.stop()
        announce = await interaction.followup.send(
            f"🎲 Xúc xắc: {first.mention} **đi trước**, "
            f"{second.mention} đi sau.\nTiếp theo: chọn đội hình!"
        )
        self.session.announce_msgs.append(announce)
        await _begin_selection(interaction, self.session, "A")

    @discord.ui.button(label="❌ Từ chối", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.target.id:
            await _ephemerals.send(
                interaction, "Chỉ người được thách đấu mới được từ chối!"
            )
            return
        if self.session.cancelled or self.session.done:
            return
        self.session.cancelled = True
        _release_session(self.session)
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(
            content=f"❌ {self.session.target.mention} đã từ chối thách đấu.",
            view=self,
        )
        self.stop()
        self.session.done = True

    @discord.ui.button(label="🚫 Hủy", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.challenger.id:
            await _ephemerals.send(interaction, "Chỉ người thách đấu mới được hủy!")
            return
        if self.session.cancelled or self.session.done:
            return
        self.session.cancelled = True
        _release_session(self.session)
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(
            content=f"🚫 {interaction.user.mention} đã hủy thách đấu.",
            view=self,
        )
        self.stop()


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
        cancel = discord.ui.Button(label="🚫 Hủy trận", style=discord.ButtonStyle.danger, row=1)
        cancel.callback = self._cancel
        self.add_item(cancel)

    async def _cancel(self, interaction: discord.Interaction):
        session = self.session
        if session.cancelled or session.done:
            return
        if interaction.user.id not in (session.challenger.id, session.target.id):
            await _ephemerals.send(interaction, "Em không phải người trong trận!")
            return
        session.cancelled = True
        _release_session(session)
        await interaction.response.defer()
        other = (
            session.target if interaction.user.id == session.challenger.id
            else session.challenger
        )
        for m in session.select_msgs:
            try:
                await m.delete()
            except Exception:
                pass
        for m in session.announce_msgs:
            try:
                await m.delete()
            except Exception:
                pass
        try:
            await session.channel.send(
                f"🚫 {interaction.user.mention} đã hủy trận với {other.mention} trong lúc chọn đội."
            )
        except Exception:
            pass

    async def on_timeout(self):
        if self.session.cancelled or self.session.done:
            return
        self.session.cancelled = True
        _release_session(self.session)
        for item in self.children:
            item.disabled = True
        await _cancel_team_select(self.session)

    async def _on_select(self, interaction: discord.Interaction):
        if self.session.cancelled or self.session.done:
            await interaction.response.send_message(
                "⏳ Trận đã bị hủy!", ephemeral=True
            )
            return
        expected = self.session.user_for_side(self.side).id
        if interaction.user.id != expected:
            await _ephemerals.send(interaction, "Không phải lượt chọn của em!")
            return
        vals = interaction.data.get("values", [])
        chosen = [get_card(v) for v in vals]
        if self.side == "A":
            self.session.a_cards = chosen
            self.session.a_levels = {
                v: await get_char_level(self.session.user_for_side("A").id, v)
                for v in vals
            }
        else:
            self.session.b_cards = chosen
            self.session.b_levels = {
                v: await get_char_level(self.session.user_for_side("B").id, v)
                for v in vals
            }
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()
        conf = await interaction.followup.send(
            content=f"✅ {interaction.user.mention} đã chốt đội!",
            embeds=_team_preview_cards(interaction.user, chosen),
            ephemeral=True,
        )
        self.session.confirm_msgs.append(conf)
        if self.side == "A":
            await _begin_selection(interaction, self.session, "B")
        else:
            for m in self.session.select_msgs:
                try:
                    await m.delete()
                except Exception:
                    pass
            await _resolve(self.session, interaction)


async def _begin_selection(interaction, session: PVPSession, side: str):
    if session.cancelled or session.done:
        return
    user = session.user_for_side(side)
    rows = await get_collection(user.id)
    owned = {r["char_key"]: r["dup_count"] for r in rows}
    lvls = {r["char_key"]: r["lvl"] for r in rows}
    cards = [c for k in owned if (c := get_card(k))]
    if len(cards) < PVP_TEAM_SIZE:
        session.cancelled = True
        _release_session(session)
        await interaction.followup.send(
            f"{user.mention} cần ít nhất **{PVP_TEAM_SIZE}** thẻ để đấu "
            f"(hiện có {len(cards)} thẻ)! Quay gacha nữa nè 🎴",
            ephemeral=True,
        )
        await _cancel_team_select(session)
        return
    cards.sort(key=lambda c: (not c["rarity"].startswith("5"), c["rarity"], c["name"]))
    max_pick = min(PVP_TEAM_SIZE, len(cards))
    options = [
        discord.SelectOption(
            label=f"{c['name']} Lv{lvls.get(c['key'], 1)} ({'5★' if c['rarity'].startswith('5') else '4★'})",
            value=c["key"],
            description=f"{ROLE_LABEL[c['role']]} • {element_name(c['element'])}",
            emoji=ELEMENT_EMOJI.get(c["element"], "❔"),
        )
        for c in cards
    ]
    view = TeamSelectView(session, side, options, max_pick)
    msg = await interaction.followup.send(
        f"{user.mention} chọn **{max_pick}** thẻ để lập đội "
        f"(từ **{len(cards)}** thẻ đang có):",
        view=view,
    )
    session.select_msgs.append(msg)


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
        self.btn_surrender = discord.ui.Button(label="🏳️ Đầu hàng", style=discord.ButtonStyle.danger)
        self.btn_normal.callback = lambda i: self._act(i, "normal")
        self.btn_skill.callback = lambda i: self._act(i, "skill")
        self.btn_ult.callback = lambda i: self._act(i, "ultimate")
        self.btn_surrender.callback = self._surrender
        self.add_item(self.btn_normal)
        self.add_item(self.btn_skill)
        self.add_item(self.btn_ult)
        if pending is not None:
            self.btn_skip_pending = discord.ui.Button(label="⏭️ Bỏ đánh thường", style=discord.ButtonStyle.secondary)
            self.btn_skip_pending.callback = self._skip_pending
            self.add_item(self.btn_skip_pending)
        self.add_item(self.btn_surrender)

    def _add_selects(self, chars: list, enemies: list):
        if chars:
            self.char_select = discord.ui.Select(
                placeholder="① Chọn thẻ hành động",
                min_values=1, max_values=1,
                options=[discord.SelectOption(
                    label=f.name, value=f.key,
                    description=f"{ROLE_LABEL[f.role]} • {element_name(f.element)}",
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
        if interaction.user.id in (self.battle.a_user.id, self.battle.b_user.id):
            return True
        await _ephemerals.send(interaction, "Em không phải người trong trận!")
        return False

    async def _surrender(self, interaction: discord.Interaction):
        battle = self.battle
        if battle.done:
            return
        if interaction.user.id == battle.a_user.id:
            winner = "B"
        elif interaction.user.id == battle.b_user.id:
            winner = "A"
        else:
            await _ephemerals.send(interaction, "Em không phải người trong trận!")
            return
        for it in self.children:
            it.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()
        await _finish_battle(battle, winner, surrender=True)

    async def _skip_pending(self, interaction: discord.Interaction):
        battle = self.battle
        if battle.done:
            return
        if interaction.user.id != battle._owner_active().id:
            await _ephemerals.send(interaction, "⚠️ Không phải lượt của em!")
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
        if interaction.user.id != battle._owner_active().id:
            await _ephemerals.send(interaction, "⚠️ Không phải lượt của em!")
            return
        char_select = getattr(self, "char_select", None)
        target_select = getattr(self, "target_select", None)
        char_key = char_select.values[0] if (char_select and char_select.values) else None
        if char_key is None:
            await _ephemerals.send(
                interaction, "⚠️ Hãy chọn ① thẻ hành động trước khi bấm nút!"
            )
            return
        actor = next((f for f in battle._active_team() if f.key == char_key), None)
        if actor is None or not actor.alive:
            await _ephemerals.send(
                interaction, "⚠️ Thẻ này đã bị hạ gục, không thể hành động!"
            )
            return
        if actor.turn_done:
            await _ephemerals.send(
                interaction,
                f"✅ {actor.name} đã kết thúc hành động trong lượt này, hãy chọn thẻ khác!",
            )
            return
        if actor.stunned:
            await _ephemerals.send(
                interaction, f"⭐ {actor.name} đang bị choáng, không thể hành động!"
            )
            return

        pending = battle.pending_actor(battle._active_team())
        if pending is not None and pending is not actor:
            await _ephemerals.send(
                interaction,
                f"🔒 {pending.name} vừa dùng skill và còn 1 hành động nữa — "
                f"hãy đánh thường / ulti / bỏ đánh thường cho {pending.name} trước!",
            )
            return
        if action == "skill" and actor.pending:
            await _ephemerals.send(
                interaction,
                f"🔥 {actor.name} đã dùng skill rồi, hãy đánh thường, ulti hoặc bỏ đánh thường để hoàn tất!",
            )
            return

        eff = actor.skill if action == "skill" else (actor.ultimate if action == "ultimate" else None)
        needs_target = action == "normal" or (eff is not None and eff["type"] in (
            "ST_DMG", "STUN", "HEAL_ST_DMG",
            "ST_DMG_DEBUFF", "AOE_DMG_STUN", "ST_LIFESTEAL", "STUN_ST_DMG",
        ))
        target = None
        if needs_target:
            tkey = target_select.values[0] if (target_select and target_select.values) else None
            if tkey is None:
                await _ephemerals.send(
                    interaction, "⚠️ Hãy chọn ② đối tượng (mục tiêu) để tấn công trước!"
                )
                return
            target = next((e for e in battle._enemy_of(actor) if e.key == tkey and e.alive), None)
            if target is None:
                await _ephemerals.send(
                    interaction,
                    "⚠️ Mục tiêu đã chọn không hợp lệ (có thể đã bị hạ gục)!",
                )
                return

        sp = battle._sp_of(actor)
        if action == "skill" and sp <= 0:
            await _ephemerals.send(
                interaction,
                "🔥 Không đủ Skill Point để dùng skill! (hết SP, hãy đánh thường để nạp)",
            )
            return
        if action == "ultimate" and actor.energy < PVP_ENERGY_MAX:
            await _ephemerals.send(
                interaction,
                f"⚡ Không đủ năng lượng để dùng Ultimate! "
                f"({actor.energy}/{PVP_ENERGY_MAX} — đánh thường hoặc skill để nạp)",
            )
            return
        if not battle.apply_action(actor, action, target):
            await _ephemerals.send(
                interaction, "⚠️ Không thể thực hiện hành động này!"
            )
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
    if session.cancelled or session.done or not session.a_cards or not session.b_cards:
        return
    pending_challenges.discard(_challenge_key(session.challenger.id, session.target.id))
    session.done = True

    battle = BattleSession(
        session.a_cards, session.b_cards,
        session.user_for_side("A"), session.user_for_side("B"),
        interaction.channel, interaction.client,
        a_levels=session.a_levels, b_levels=session.b_levels,
    )
    battle.confirm_msgs = session.confirm_msgs
    battle.announce_msgs = session.announce_msgs
    anim = discord.Embed(title="⚔️ Bắt đầu!", color=PVP_COLOR)
    anim.set_image(url=PVP_BATTLE_ANIM_GIF)
    anim_msg = await interaction.followup.send(embed=anim)
    img_task = asyncio.create_task(prepare_battle_image(battle))
    await asyncio.sleep(2.5)
    try:
        await anim_msg.delete()
    except Exception:
        pass
    try:
        await img_task
    except Exception:
        pass

    battle.message = await interaction.channel.send(
        embed=discord.Embed(title="⚔️ Đang vào trận...", color=PVP_COLOR)
    )
    await _post_panel(battle)
    # Preview đội hình (confirm_msgs) được GIỮ LẠI xuyên suốt trận đấu,
    # chỉ bị xóa khi trận kết thúc (xem _finish_battle).
    await _ephemerals.flush()


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
    kwargs = {"embed": embed, "view": ControlPanelView(battle)}
    if battle._img_ok:
        try:
            # Message.edit() dùng "attachments", KHÔNG phải "files" (khác với Messageable.send())
            kwargs["attachments"] = [discord.File(render_battle_image(battle), filename="battle.png")]
        except Exception as e:
            print("LỖI RENDER_IMAGE:", e, flush=True)
            battle._img_ok = False
            kwargs["embed"] = _battle_embed(battle)
    try:
        await battle.message.edit(**kwargs)
    except Exception as e:
        print("LỖI POST_PANEL:", e, flush=True)


async def _after_action(battle: BattleSession):
    w = battle.check_winner()
    if w is not False:
        await _finish_battle(battle, w)
        return
    # Xen kẽ: sau MỖI hành động đơn lẻ, đổi lượt sang bên đối diện —
    # trừ khi thẻ vừa dùng skill còn nợ 1 hành động (pending), lúc đó
    # vẫn giữ lượt cho team đó để đánh nốt.
    new_round = battle.advance_turn()
    await _post_panel(battle)
    if new_round and battle.log:
        await _notify_turn_log(battle)


async def _notify_turn_log(battle: BattleSession):
    """Gửi thông báo riêng tóm tắt diễn biến của vòng vừa kết thúc."""
    if battle.done or not battle.channel or not battle.log:
        return
    try:
        log = battle.log
        e = discord.Embed(
            title=f"📜 Diễn biến vòng {battle.round - 1}",
            color=PVP_COLOR,
        )
        e.set_author(name="Chị Cá 🐟 PvP")
        shown = log[:12] + (["..."] if len(log) > 12 else [])
        e.description = "```" + "\n".join(shown) + "```"
        e.set_footer(text=f"⚔️ Đến lượt {battle._owner_active().display_name}")
        msg = await battle.channel.send(embed=e)
        battle.turn_log_msgs.append(msg)
        battle.log = []
    except Exception as err:
        print("LỖI NOTIFY_TURN_LOG:", err, flush=True)


async def _finish_battle(battle: BattleSession, winner, surrender: bool = False):
    battle.done = True
    await _ephemerals.flush()
    active_players.discard(battle.a_user.id)
    active_players.discard(battle.b_user.id)
    for m in battle.turn_log_msgs:
        try:
            await m.delete()
        except Exception:
            pass
    battle.turn_log_msgs.clear()
    for m in getattr(battle, "confirm_msgs", []):
        try:
            await m.delete()
        except Exception:
            pass
    for m in getattr(battle, "announce_msgs", []):
        try:
            await m.delete()
        except Exception:
            pass
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

    if draw:
        await update_pvp_result(battle.a_user.id, battle.b_user.id, na, nb, draw)
    else:
        w_new = nb if win_user.id == battle.b_user.id else na
        l_new = nb if lose_user.id == battle.b_user.id else na
        await update_pvp_result(win_user.id, lose_user.id, w_new, l_new, draw)

    embed = _result_embed(battle, ra, na, rb, nb, win_user, lose_user, draw, surrender)
    send_kwargs = {"embed": embed}
    if battle._img_ok:
        try:
            send_kwargs["file"] = discord.File(render_battle_image(battle), filename="battle.png")
        except Exception:
            pass
    try:
        await battle.channel.send(**send_kwargs)
    except Exception as e:
        print("LỖI FINISH_BATTLE:", e, flush=True)
    if battle.message is not None:
        try:
            await battle.message.delete()
        except Exception:
            pass


# ====================== EMBEDS ======================
def _effect_desc(eff: dict) -> str:
    t = eff.get("type")
    p = eff.get("power", 0)
    p2 = eff.get("power2", 0)
    if t == "ST_DMG":
        return f"Gây sát thương đơn mục tiêu (~x{p:.2f} ATK)"
    if t == "AOE_DMG":
        return f"Gây sát thương toàn bộ địch (~x{p:.2f} ATK)"
    if t == "SHIELD_TEAM":
        return f"Toàn đội giáp chặn +{int(p*100)}%"
    if t == "HEAL":
        return f"Hồi {p} HP cho đồng đội thấp máu nhất"
    if t == "BUFF_ATK":
        return f"Toàn đội +{int(p*100)}% ATK"
    if t == "BUFF_SPD":
        return f"Toàn đội +{p} SPD"
    if t == "DEBUFF_DEF":
        return f"Địch nhận thêm +{int(p*100)}% sát thương"
    if t == "STUN":
        return "Choáng mục tiêu 1 lượt"
    if t == "SHIELD_HEAL":
        return f"Giáp chặn +{int(p*100)}% và hồi {p2} HP đồng đội thấp máu"
    if t == "HEAL_ST_DMG":
        return f"Hồi {p} HP đồng đội thấp máu và gây sát thương đơn mục tiêu"
    if t == "HEAL_BUFF":
        return f"Hồi {p} HP đồng đội thấp máu và toàn đội +{int(p2*100)}% ATK"
    if t == "ST_DMG_DEBUFF":
        return f"Sát thương đơn mục tiêu (~x{p:.2f} ATK) + địch nhận thêm +{int(p2*100)}% sát thương"
    if t == "AOE_DMG_DEBUFF":
        return f"Sát thương toàn địch (~x{p:.2f} ATK) + mọi địch nhận thêm +{int(p2*100)}% sát thương"
    if t == "AOE_DMG_STUN":
        return f"Sát thương toàn địch (~x{p:.2f} ATK) + choáng mục tiêu 1 lượt"
    if t == "ST_LIFESTEAL":
        return f"Sát thương đơn mục tiêu (~x{p:.2f} ATK) + hút {int(p2*100)}% sát thương thành máu"
    if t == "HEAL_ENERGY":
        return f"Hồi {p} HP đồng đội thấp máu + toàn đội nạp +{p2} nộ khí"
    if t == "ENERGY_DEBUFF":
        return f"Toàn đội nạp +{p2} nộ khí + mọi địch nhận thêm +{int(p*100)}% sát thương"
    if t == "STUN_ST_DMG":
        return f"Choáng mục tiêu 1 lượt + gây sát thương đơn (~x{p:.2f} ATK)"
    return eff.get("name", "Kỹ năng")


def _card_stats(card, lvl):
    bonus = lvl - 1
    return (
        card["hp"] + LEVEL_HP_BONUS * bonus,
        card["atk"] + LEVEL_ATK_BONUS * bonus,
        card["spd"] + LEVEL_SPD_BONUS * bonus,
    )


def _card_info_embed(card, owned_count, lvl=1):
    stars = "★★★★★" if card["rarity"].startswith("5") else "★★★★"
    hp, atk, spd = _card_stats(card, lvl)
    e = discord.Embed(
        title=f"{ELEMENT_EMOJI.get(card['element'], '❔')} {card['name']} Lv{lvl} [{ROLE_LABEL[card['role']]}]",
        color=PVP_COLOR,
    )
    try:
        e.set_thumbnail(url=card["url"])
    except Exception:
        pass
    e.add_field(
        name=f"{stars} {element_name(card['element'])}",
        value="\u200b",
        inline=False,
    )
    e.add_field(
        name=f"❤️ HP: {hp} · ⚔️ ATK: {atk} · 💨 SPD: {spd}",
        value="\u200b",
        inline=False,
    )
    e.add_field(name=f"🔥 Skill · {card['skill']['name']}", value=_effect_desc(card["skill"]), inline=False)
    e.add_field(name=f"✨ Ultimate · {card['ultimate']['name']}", value=_effect_desc(card["ultimate"]), inline=False)
    e.set_footer(text=f"💠 Đã sở hữu x{owned_count}")
    return e


def _level_up_embed(card, lvl, mora):
    e = discord.Embed(
        title=f"⬆️ Nâng cấp {card['name']}",
        description=f"**Cấp {lvl}/{CHAR_MAX_LEVEL}**\n{_bar(lvl, CHAR_MAX_LEVEL, 15)}",
        color=PVP_COLOR,
    )
    try:
        e.set_thumbnail(url=card["url"])
    except Exception:
        pass
    hp, atk, spd = _card_stats(card, lvl)
    e.add_field(name="❤️ HP", value=f"{hp}", inline=True)
    e.add_field(name="⚔️ ATK", value=f"{atk}", inline=True)
    e.add_field(name="💨 SPD", value=f"{spd:.1f}", inline=True)
    e.add_field(
        name="⚡ Tăng mỗi cấp",
        value=f"+{LEVEL_HP_BONUS} HP · +{LEVEL_ATK_BONUS} ATK · +{LEVEL_SPD_BONUS} SPD",
        inline=False,
    )
    if lvl < CHAR_MAX_LEVEL:
        cost = LEVEL_COST_PER
        e.add_field(
            name="💰 Chi phí",
            value=f"{cost}🪙 / cấp  ·  Em có **{mora}🪙**",
            inline=False,
        )
    else:
        e.add_field(name="🏆", value="Đã đạt **MAX LEVEL** 🎉", inline=False)
    return e


class LevelUpView(discord.ui.View):
    def __init__(self, author, card, lvl, owned_count=1):
        super().__init__(timeout=180)
        self.author = author
        self.card = card
        self.lvl = lvl
        self.owned_count = owned_count
        self.mode = "card"
        self._build_card_mode()

    def _build_card_mode(self):
        self.clear_items()
        self.btn_level = discord.ui.Button(label="⬆️ Lên cấp", style=discord.ButtonStyle.success)
        self.btn_level.callback = self._open_level
        self.btn_const = discord.ui.Button(label="🔮 Cung mệnh (sớm)", style=discord.ButtonStyle.secondary, disabled=True)
        self.btn_const.callback = self._constellation
        self.add_item(self.btn_level)
        self.add_item(self.btn_const)

    def _build_level_mode(self):
        self.clear_items()
        self.btn_back = discord.ui.Button(label="◀️ Quay lại", style=discord.ButtonStyle.secondary)
        self.btn_back.callback = self._back
        self.btn_1 = discord.ui.Button(label=f"⬆️ +1 ({LEVEL_COST_PER}🪙)", style=discord.ButtonStyle.primary)
        self.btn_1.callback = lambda i: self._level_up(i, 1)
        self.btn_10 = discord.ui.Button(label=f"⬆️ +10 ({LEVEL_COST_PER*10}🪙)", style=discord.ButtonStyle.primary)
        self.btn_10.callback = lambda i: self._level_up(i, 10)
        self.btn_1.disabled = self.lvl >= CHAR_MAX_LEVEL
        self.btn_10.disabled = self.lvl >= CHAR_MAX_LEVEL
        self.add_item(self.btn_back)
        self.add_item(self.btn_1)
        self.add_item(self.btn_10)

    async def _refresh(self, interaction, embed):
        try:
            await interaction.response.edit_message(embed=embed, view=self)
        except Exception:
            pass

    async def _open_level(self, interaction):
        if interaction.user.id != self.author.id:
            await _ephemerals.send(interaction, "Không phải thẻ của em!")
            return
        self.mode = "level"
        self._build_level_mode()
        mora = await get_mora(self.author.id)
        await self._refresh(interaction, _level_up_embed(self.card, self.lvl, mora))

    async def _back(self, interaction):
        if interaction.user.id != self.author.id:
            await _ephemerals.send(interaction, "Không phải thẻ của em!")
            return
        self.mode = "card"
        self._build_card_mode()
        await self._refresh(interaction, _card_info_embed(self.card, self.owned_count, self.lvl))

    async def _constellation(self, interaction):
        await _ephemerals.send(interaction, "🔮 Cung mệnh sắp ra mắt, đợi chị nhé 🐟")

    async def _level_up(self, interaction, amount):
        if interaction.user.id != self.author.id:
            await _ephemerals.send(interaction, "Không phải thẻ của em!")
            return
        if self.lvl >= CHAR_MAX_LEVEL:
            await _ephemerals.send(interaction, "🏆 Đã MAX LEVEL rồi em!")
            return
        remaining = CHAR_MAX_LEVEL - self.lvl
        actual = min(amount, remaining)
        cost = LEVEL_COST_PER * actual
        mora = await get_mora(self.author.id)
        if mora < cost:
            await _ephemerals.send(
                interaction,
                f"⚠️ Thiếu **{cost - mora}🪙** mora để nâng (cần {cost}🪙)!",
            )
            return
        ok = await spend_mora(self.author.id, cost)
        if not ok:
            await _ephemerals.send(interaction, "⚠️ Không đủ mora để nâng cấp!")
            return
        new_lvl = self.lvl + actual
        await set_char_level(self.author.id, self.card["key"], new_lvl)
        self.lvl = new_lvl
        self._build_level_mode()
        mora = await get_mora(self.author.id)
        await self._refresh(interaction, _level_up_embed(self.card, self.lvl, mora))

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message is not None:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass


async def handle_card_info(channel, author, card):
    rows = await get_collection(author.id)
    owned = {r["char_key"]: r["dup_count"] for r in rows}
    count = owned.get(card["key"], 0)
    if count == 0:
        await channel.send(
            f"🔒 Em chưa sở hữu **{card['name']}**! Quay gacha nè 🎴"
        )
        return
    lvl = await get_char_level(author.id, card["key"])
    view = LevelUpView(author, card, lvl, count)
    msg = await channel.send(embed=_card_info_embed(card, count, lvl), view=view)
    view.message = msg


def _team_preview_cards(user, cards) -> list:
    embeds = []
    for c in cards:
        e = discord.Embed(
            title=f"{ELEMENT_EMOJI.get(c['element'],'❔')} {c['name']} [{ROLE_LABEL[c['role']]}]",
            color=PVP_COLOR,
        )
        try:
            e.set_thumbnail(url=c["url"])
        except Exception:
            pass
        e.add_field(name=f"❤️ HP: {c['hp']} · ⚔️ ATK: {c['atk']} · 💨 SPD: {c['spd']}", value="\u200b", inline=False)
        e.add_field(name=f"🔥 Skill · {c['skill']['name']}", value=_effect_desc(c["skill"]), inline=False)
        e.add_field(name=f"✨ Ultimate · {c['ultimate']['name']}", value=_effect_desc(c["ultimate"]), inline=False)
        embeds.append(e)
    return embeds


def _sp_of_team(battle, team):
    return battle.sp_a if team == "A" else battle.sp_b


def _fighter_status_mark(f):
    if not f.alive:
        return "💀"
    if f.stunned:
        return "⭐"
    if f.turn_done:
        return "✅"
    return "❤️"


def _fighter_field(e, f):
    mark = _fighter_status_mark(f)
    badge = f"{ELEMENT_EMOJI.get(f.element,'❔')}"
    e.add_field(
        name=f"{mark} {badge} {f.name} Lv{f.lvl}",
        value=_fighter_card_value(f),
        inline=True,
    )


def _fighter_card_value(f):
    if not f.alive:
        return "Đã hạ gục"
    lines = [f"{_bar(max(0, f.hp), f.max_hp)} {max(0,f.hp)}/{f.max_hp}"]
    extras = [f"⚡{f.energy}/{PVP_ENERGY_MAX}"]
    if f.shield > 0:
        extras.append(f"🛡️{f.shield}")
    if f.pending:
        extras.append("↻\u00a01 hành động")
    lines.append(" ".join(extras))
    return "\n".join(lines)


def _battle_embed(battle: BattleSession):
    owner = battle._owner_active()
    e = discord.Embed(title=f"⚔️ PVP — LƯỢT {owner.display_name.upper()}", color=PVP_COLOR)
    try:
        e.set_author(name=f"ĐẾN LƯỢT: {owner.display_name.upper()}", icon_url=owner.display_avatar.url)
    except Exception:
        e.set_author(name=f"ĐẾN LƯỢT: {owner.display_name.upper()}")
    sp = battle.sp_a if battle.active_team == "A" else battle.sp_b
    if battle._img_ok:
        e.set_image(url="attachment://battle.png")
    else:
        e.add_field(
            name=f"🔵 ĐỘI HÌNH CỦA {battle.a_user.display_name.upper()}",
            value=f"🔋 SP {_sp_of_team(battle, 'A')}/{PVP_SP_MAX}",
            inline=False,
        )
        for f in battle.team_a:
            _fighter_field(e, f)
        e.add_field(
            name=f"🔴 ĐỘI HÌNH CỦA {battle.b_user.display_name.upper()}",
            value=f"🔋 SP {_sp_of_team(battle, 'B')}/{PVP_SP_MAX}",
            inline=False,
        )
        for f in battle.team_b:
            _fighter_field(e, f)
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


def _result_embed(battle, a_old, a_new, b_old, b_new, win_user, lose_user, draw, surrender=False):
    if draw:
        title = "🤝 ĐÃ HÒA!"
        color = 0x95A5A6
    elif surrender:
        title = f"🏆 {win_user.display_name} THẮNG!"
        color = 0xE67E22
    else:
        title = f"🏆 {win_user.display_name} THẮNG!"
        color = PVP_COLOR
    e = discord.Embed(title=title, color=color)
    e.set_author(name="Chị Cá 🐟 PvP")
    if surrender and lose_user is not None:
        e.description = f"🏳️ {lose_user.mention} đã đầu hàng."

    if draw:
        e.add_field(
            name=f"🔵 {battle.a_user.display_name} ({_signed(a_new - a_old)})",
            value=f"Bậc ELO **{a_old} → {a_new}**",
            inline=True,
        )
        e.add_field(
            name=f"🔴 {battle.b_user.display_name} ({_signed(b_new - b_old)})",
            value=f"Bậc ELO **{b_old} → {b_new}**",
            inline=True,
        )
        e.set_footer(text="Hòa, không đổi ELO")
        return e

    if win_user.id == battle.a_user.id:
        w_old, w_new, l_old, l_new = a_old, a_new, b_old, b_new
    else:
        w_old, w_new, l_old, l_new = b_old, b_new, a_old, a_new

    e.add_field(
        name=f"🏆 {win_user.display_name} ({_signed(w_new - w_old)})",
        value=f"Bậc ELO **{w_old} → {w_new}**",
        inline=True,
    )
    e.add_field(
        name=f"💀 {lose_user.display_name} ({_signed(l_new - l_old)})",
        value=f"Bậc ELO **{l_old} → {l_new}**",
        inline=True,
    )
    e.set_footer(text=f"🎉 Chúc mừng {win_user.display_name} chiến thắng!")
    return e


# ====================== ENTRY POINTS ======================
async def start_pvp_challenge(message, bot):
    target = message.mentions[0] if message.mentions else None
    if target is None:
        await message.channel.send(
            "Em cần mention người muốn thách đấu: `chị cá pvp @người_chơi` 🐟",
            reference=message, mention_author=False,
        )
        return
    if target.bot:
        await message.channel.send("Không thể thách đấu bot! 🐟", reference=message, mention_author=False)
        return
    if target.id == message.author.id:
        await message.channel.send("Em không thể tự thách đấu chính mình 😅", reference=message, mention_author=False)
        return
    key = _challenge_key(message.author.id, target.id)
    if key in pending_challenges:
        await message.channel.send("Đã có một thách đấu đang chờ giữa hai em! ⏳", reference=message, mention_author=False)
        return
    if message.author.id in active_players:
        await message.channel.send(
            "Em đang tham gia một trận PvP rồi (chọn đội/đang đánh)! Xong hẵng thách tiếp nhé 🐟",
            reference=message, mention_author=False,
        )
        return
    if target.id in active_players:
        await message.channel.send(
            "Người đó đang bận một trận PvP rồi, đợi chút nhé! ⏳",
            reference=message, mention_author=False,
        )
        return

    rows_a = await get_collection(message.author.id)
    rows_b = await get_collection(target.id)
    if len(rows_a) < PVP_TEAM_SIZE:
        await message.channel.send(
            f"{message.author.mention} cần ít nhất **{PVP_TEAM_SIZE}** thẻ để đấu "
            f"(hiện có {len(rows_a)} thẻ)! Quay gacha nữa nè 🎴",
            reference=message, mention_author=False,
        )
        return
    if len(rows_b) < PVP_TEAM_SIZE:
        await message.channel.send(
            f"{target.mention} cần ít nhất **{PVP_TEAM_SIZE}** thẻ để đấu "
            f"(hiện có {len(rows_b)} thẻ) 🎴",
            reference=message, mention_author=False,
        )
        return

    pending_challenges.add(key)
    active_players.add(message.author.id)
    active_players.add(target.id)
    session = PVPSession(message.author, target, message.channel)

    e = discord.Embed(
        title="⚔️ THÁCH ĐẤU PvP",
        description=f"{message.author.mention} thách đấu {target.mention}!\n"
        f"{target.mention} có 60 giây để chấp nhận.",
        color=PVP_COLOR,
    )
    e.set_author(name="Chị Cá 🐟 PvP")
    e.set_thumbnail(url=PVP_CHALLENGE_GIF)
    e.set_footer(text="Mỗi lượt: chọn thẻ + mục tiêu + hành động (Đánh thường/Skill/Ultimate) · SP chung team")
    view = ChallengeView(session)
    msg = await message.channel.send(embed=e, view=view, reference=message, mention_author=False)
    view.message = msg


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
                    value=f"⭐ ELO **{r['rating']}** · {r['wins']}W/{r['losses']}L",
                    inline=False,
                )
        await message.channel.send(embed=e, reference=message, mention_author=False)
        return

    target = message.mentions[0] if message.mentions else message.author
    row = await get_pvp_rating(target.id)
    rating = row["rating"]
    wins = row["wins"]
    losses = row["losses"]
    e = discord.Embed(title=f"⭐ Hạng PvP của {target.display_name}", color=PVP_COLOR)
    e.set_author(name="Chị Cá 🐟 PvP")
    e.set_thumbnail(url=target.display_avatar.url)
    e.add_field(name="ELO", value=f"**{rating}**", inline=True)
    e.add_field(name="Thắng", value=f"{wins}", inline=True)
    e.add_field(name="Thua", value=f"{losses}", inline=True)
    e.set_footer(text="Thắng +ELO, thua -ELO (K=32)")
    await message.channel.send(embed=e, reference=message, mention_author=False)