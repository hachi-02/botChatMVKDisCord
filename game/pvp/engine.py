import random

from config import PVP_ENERGY_MAX, PVP_MAX_ROUND, PVP_SP_START, PVP_SP_MAX, PVP_DODGE_FACTOR, PVP_DODGE_CAP

from .cards import ELEMENT_ADVANTAGE, ELEM_STRONG, ELEM_WEAK


class Fighter:
    def __init__(self, card: dict, lvl: int = 1):
        self.key = card["key"]
        self.name = card["name"]
        self.url = card["url"]
        self.rarity = card["rarity"]
        self.role = card["role"]
        self.element = card["element"]
        self.lvl = lvl
        bonus = lvl - 1
        self.atk = card["atk"] + 2 * bonus
        self.max_hp = card["hp"] + 10 * bonus
        self.hp = self.max_hp
        self.spd = card["spd"] + 0.2 * bonus
        self.crit_rate = card["crit_rate"]
        self.crit_dmg = card["crit_dmg"]
        self.skill = card["skill"]
        self.ultimate = card["ultimate"]
        self.energy = 0
        self.atk_buff = 0.0
        self.def_debuff = 0.0
        self.shield = 0.0
        self.stunned = False
        self.turn_done = False
        self.pending = False

    @property
    def alive(self) -> bool:
        return self.hp > 0

    def gain_energy(self, n: int):
        self.energy = min(PVP_ENERGY_MAX, self.energy + n)


def _elem_mult(att_elem: str, def_elem: str) -> float:
    if def_elem in ELEMENT_ADVANTAGE.get(att_elem, set()):
        return ELEM_STRONG
    if att_elem in ELEMENT_ADVANTAGE.get(def_elem, set()):
        return ELEM_WEAK
    return 1.0


def _compute_damage(attacker: Fighter, defender: Fighter, mult: float):
    if random.random() < min(PVP_DODGE_CAP, defender.spd * PVP_DODGE_FACTOR / 100):
        return 0, False, True
    base = (
        attacker.atk
        * (1 + attacker.atk_buff)
        * _elem_mult(attacker.element, defender.element)
        * random.uniform(0.85, 1.15)
        * mult
    )
    if attacker.role == "DPS" and attacker.hp == attacker.max_hp:
        base *= 1.10
    crit = random.random() < attacker.crit_rate
    if crit:
        base *= attacker.crit_dmg
    dmg = max(1, round(base))
    reduction = defender.shield + (0.15 if defender.role == "TANK" else 0.0)
    dmg = max(1, round(dmg * (1 - min(reduction, 0.6))))
    dmg = round(dmg * (1 + defender.def_debuff))
    dmg = max(1, dmg)
    defender.hp -= dmg
    defender.gain_energy(10)
    return dmg, crit, False


def _lowest_alive(team: list):
    alive = [f for f in team if f.alive]
    if not alive:
        return None
    return min(alive, key=lambda f: f.hp / f.max_hp)


def _apply_effect(caster: Fighter, team: list, enemy: list, eff: dict, log: list, target=None):
    t = eff["type"]
    p = eff.get("power", 0)
    p2 = eff.get("power2", 0)
    tag = f"🔮 **{caster.name}** → **{eff['name']}**"
    if t == "ST_DMG":
        if target and target.alive:
            dmg, crit, dodged = _compute_damage(caster, target, p)
            if dodged:
                log.append(f"{tag}: {target.name} né đòn 💨")
            else:
                log.append(f"{tag}: {target.name} mất {dmg} HP{' 💥' if crit else ''}")
    elif t == "AOE_DMG":
        for e in enemy:
            if e.alive:
                dmg, crit, dodged = _compute_damage(caster, e, p)
                if dodged:
                    log.append(f"{tag}: {e.name} né đòn 💨")
                else:
                    log.append(f"{tag}: {e.name} -{dmg} HP{' 💥' if crit else ''}")
    elif t == "SHIELD_TEAM":
        for ally in team:
            ally.shield = max(ally.shield, p)
        log.append(f"{tag}: toàn đội giáp giảm {int(p*100)}% 🛡️")
    elif t == "HEAL":
        low = _lowest_alive(team)
        if low is not None:
            before = low.hp
            low.hp = min(low.max_hp, low.hp + p)
            log.append(f"{tag}: hồi {low.hp - before} HP cho {low.name} 💚")
    elif t == "BUFF_ATK":
        for ally in team:
            ally.atk_buff += p
        log.append(f"{tag}: toàn đội +{int(p*100)}% ATK ⬆️")
    elif t == "BUFF_SPD":
        for ally in team:
            ally.spd += p
        log.append(f"{tag}: toàn đội +{p} SPD")
    elif t == "DEBUFF_DEF":
        for e in enemy:
            e.def_debuff += p
        log.append(f"{tag}: địch nhận +{int(p*100)}% sát thương 🔻")
    elif t == "STUN":
        if target and target.alive:
            target.stunned = True
            log.append(f"{tag}: {target.name} bị choáng ⭐")
    elif t == "SHIELD_HEAL":
        for ally in team:
            ally.shield = max(ally.shield, p)
        low = _lowest_alive(team)
        heal_txt = ""
        if low is not None:
            before = low.hp
            low.hp = min(low.max_hp, low.hp + p2)
            heal_txt = f" + hồi {low.hp - before} HP cho {low.name}"
        log.append(f"{tag}: giáp {int(p*100)}%{heal_txt} 🛡️💚")
    elif t == "HEAL_ST_DMG":
        low = _lowest_alive(team)
        if low is not None:
            before = low.hp
            low.hp = min(low.max_hp, low.hp + p)
            log.append(f"{tag}: hồi {low.hp - before} HP cho {low.name} 💚")
        if target and target.alive:
            dmg, crit, dodged = _compute_damage(caster, target, p2)
            if dodged:
                log.append(f"{tag}: {target.name} né đòn 💨")
            else:
                log.append(f"{tag}: {target.name} -{dmg} HP{' 💥' if crit else ''}")
    elif t == "HEAL_BUFF":
        low = _lowest_alive(team)
        heal_txt = ""
        if low is not None:
            before = low.hp
            low.hp = min(low.max_hp, low.hp + p)
            heal_txt = f"hồi {low.hp - before} HP cho {low.name} + "
        for ally in team:
            ally.atk_buff += p2
        log.append(f"{tag}: {heal_txt}toàn đội +{int(p2*100)}% ATK 💚⬆️")
    elif t == "ST_DMG_DEBUFF":
        if target and target.alive:
            dmg, crit, dodged = _compute_damage(caster, target, p)
            if dodged:
                log.append(f"{tag}: {target.name} né đòn 💨")
            else:
                target.def_debuff += p2
                log.append(f"{tag}: {target.name} -{dmg} HP{' 💥' if crit else ''} "
                           f"và nhận thêm +{int(p2*100)}% sát thương 🔻")
    elif t == "AOE_DMG_DEBUFF":
        for e in enemy:
            if e.alive:
                dmg, crit, dodged = _compute_damage(caster, e, p)
                if dodged:
                    log.append(f"{tag}: {e.name} né đòn 💨")
                else:
                    e.def_debuff += p2
                    log.append(f"{tag}: {e.name} -{dmg} HP{' 💥' if crit else ''}")
        log.append(f"{tag}: toàn địch nhận thêm +{int(p2*100)}% sát thương 🔻")
    elif t == "AOE_DMG_STUN":
        for e in enemy:
            if e.alive:
                dmg, crit, dodged = _compute_damage(caster, e, p)
                if dodged:
                    log.append(f"{tag}: {e.name} né đòn 💨")
                else:
                    log.append(f"{tag}: {e.name} -{dmg} HP{' 💥' if crit else ''}")
        if target and target.alive:
            target.stunned = True
            log.append(f"{tag}: {target.name} bị choáng ⭐")
    elif t == "ST_LIFESTEAL":
        if target and target.alive:
            dmg, crit, dodged = _compute_damage(caster, target, p)
            if dodged:
                log.append(f"{tag}: {target.name} né đòn 💨")
            else:
                heal = max(1, round(dmg * p2))
                caster.hp = min(caster.max_hp, caster.hp + heal)
                log.append(f"{tag}: {target.name} -{dmg} HP{' 💥' if crit else ''} "
                           f"và {caster.name} hút {heal} HP 💉")
    elif t == "HEAL_ENERGY":
        low = _lowest_alive(team)
        heal_txt = ""
        if low is not None:
            before = low.hp
            low.hp = min(low.max_hp, low.hp + p)
            heal_txt = f"hồi {low.hp - before} HP cho {low.name}"
        for ally in team:
            ally.gain_energy(p2)
        log.append(f"{tag}: {heal_txt} + toàn đội +{p2} nộ khí ⚡")
    elif t == "ENERGY_DEBUFF":
        for ally in team:
            ally.gain_energy(p2)
        for e in enemy:
            e.def_debuff += p
        log.append(f"{tag}: toàn đội +{p2} nộ khí ⚡, toàn địch nhận thêm +{int(p*100)}% sát thương 🔻")
    elif t == "STUN_ST_DMG":
        if target and target.alive:
            dmg, crit, dodged = _compute_damage(caster, target, p)
            if dodged:
                log.append(f"{tag}: {target.name} né đòn 💨")
            else:
                log.append(f"{tag}: {target.name} -{dmg} HP{' 💥' if crit else ''}")
            target.stunned = True
            log.append(f"{tag}: {target.name} bị choáng ⭐")


def _basic_attack(attacker: Fighter, target: Fighter, log: list):
    if target is None or not target.alive:
        log.append(f"➡️ {attacker.name} đánh thường nhưng không có mục tiêu")
        return
    dmg, crit, dodged = _compute_damage(attacker, target, 1.0)
    if dodged:
        log.append(f"💨 {target.name} né đòn của {attacker.name}!")
    else:
        log.append(
            f"➡️ {attacker.name} đánh thường {target.name}: -{dmg} HP"
            f"{' 💥 CRIT!' if crit else ''}"
        )
    attacker.gain_energy(20)


def _needs_target(eff: dict) -> bool:
    return eff["type"] in (
        "ST_DMG", "STUN", "HEAL_ST_DMG",
        "ST_DMG_DEBUFF", "AOE_DMG_STUN", "ST_LIFESTEAL", "STUN_ST_DMG",
    )


# ===================== BATTLE SESSION =====================
class BattleSession:
    def __init__(self, a_cards, b_cards, a_user, b_user, channel, bot,
                 a_levels=None, b_levels=None):
        a_levels = a_levels or {}
        b_levels = b_levels or {}
        self.team_a = [Fighter(c, a_levels.get(c["key"], 1)) for c in a_cards]
        self.team_b = [Fighter(c, b_levels.get(c["key"], 1)) for c in b_cards]
        self.a_user = a_user
        self.b_user = b_user
        self.channel = channel
        self.bot = bot
        self.active_team = "A"
        self.sp_a = PVP_SP_START
        self.sp_b = PVP_SP_START
        self.round = 1
        self.log = []
        self._img_ok = False
        self.message = None
        self.turn_log_msgs = []
        self.done = False
        self._start_rotation(self.team_a)

    def _active_team(self):
        return self.team_a if self.active_team == "A" else self.team_b

    def _enemy_of(self, fighter: Fighter):
        return self.team_b if fighter in self.team_a else self.team_a

    def _owner_active(self):
        return self.a_user if self.active_team == "A" else self.b_user

    def _sp_of(self, fighter: Fighter) -> int:
        return self.sp_a if fighter in self.team_a else self.sp_b

    def _set_sp(self, fighter: Fighter, val: int):
        if fighter in self.team_a:
            self.sp_a = val
        else:
            self.sp_b = val

    def available_chars(self, team):
        return [f for f in team if f.alive and not f.turn_done and not f.stunned]

    def pending_actor(self, team):
        """Thẻ đang chờ hành động nốt (vừa dùng skill) — nếu có thì phải xong thẻ này trước."""
        for f in team:
            if f.alive and f.pending and not f.turn_done:
                return f
        return None

    def _start_rotation(self, team):
        if any(f.alive and f.role == "SUP" for f in team):
            cands = [f for f in team if f.alive]
            if cands:
                low = min(cands, key=lambda f: f.hp / f.max_hp)
                low.hp = min(low.max_hp, low.hp + 5)

    def advance_turn(self) -> bool:
        """Chuyển lượt xen kẽ sang team đối diện sau MỖI hành động đơn lẻ.
        Nếu thẻ vừa dùng skill còn nợ 1 hành động (pending), giữ nguyên lượt
        của team đó để đánh nốt trước khi đổi bên.
        Trả về True nếu vừa mở vòng đánh mới cho team sắp có lượt (dùng để
        biết khi nào nên gửi tóm tắt diễn biến / hồi máu hỗ trợ đầu vòng)."""
        team = self._active_team()
        if self.pending_actor(team) is not None:
            return False

        self.active_team = "B" if self.active_team == "A" else "A"
        new_team = self._active_team()

        new_round = False
        if not self.available_chars(new_team):
            # Team sắp tới lượt đã dùng hết thẻ (hoặc bị choáng hết) trong vòng
            # trước đó của chính họ -> mở vòng đánh mới cho team này.
            for f in new_team:
                f.stunned = False
                f.turn_done = False
                f.pending = False
            self.round += 1
            new_round = True

        # Hồi máu hỗ trợ (SUP) mỗi khi team bắt đầu một vòng đánh mới của họ
        # (áp dụng cả cho lượt đầu tiên của mỗi bên khi vào trận).
        if all(not f.turn_done for f in new_team if f.alive):
            self._start_rotation(new_team)

        return new_round

    def end_rotation(self):
        """Giữ lại để tương thích ngược — không còn được gọi trong luồng
        xen kẽ mới (xem advance_turn)."""
        for f in self._active_team():
            f.stunned = False
        self.active_team = "B" if self.active_team == "A" else "A"
        for f in self._active_team():
            f.turn_done = False
            f.pending = False
        self.round += 1
        self._start_rotation(self._active_team())

    def apply_action(self, actor: Fighter, action: str, target: Fighter) -> bool:
        team = self._team_of(actor)
        enemy = self._enemy_of(actor)
        sp = self._sp_of(actor)
        if actor.turn_done:
            return False
        if action == "normal":
            if self.pending_actor(team) is not None and not actor.pending:
                return False
            _basic_attack(actor, target, self.log)
            sp = min(PVP_SP_MAX, sp + 1)
            actor.turn_done = True
            actor.pending = False
        elif action == "skill":
            if actor.pending or sp <= 0:
                return False
            _apply_effect(actor, team, enemy, actor.skill, self.log, target)
            actor.gain_energy(30)
            sp -= 1
            actor.pending = True
        elif action == "ultimate":
            if self.pending_actor(team) is not None and not actor.pending:
                return False
            if actor.energy < PVP_ENERGY_MAX:
                return False
            _apply_effect(actor, team, enemy, actor.ultimate, self.log, target)
            actor.energy = 0
            actor.turn_done = True
            actor.pending = False
        else:
            return False
        self._set_sp(actor, sp)
        return True

    def skip_pending(self, actor: Fighter) -> bool:
        """Bỏ qua hành động còn lại của thẻ vừa dùng skill — hoàn tất thẻ đó."""
        if actor.turn_done or not actor.pending:
            return False
        actor.turn_done = True
        actor.pending = False
        return True

    def _team_of(self, fighter: Fighter):
        return self.team_a if fighter in self.team_a else self.team_b

    def check_winner(self):
        a_alive = any(f.alive for f in self.team_a)
        b_alive = any(f.alive for f in self.team_b)
        if a_alive and not b_alive:
            return "A"
        if b_alive and not a_alive:
            return "B"
        if not a_alive and not b_alive:
            return None
        return False