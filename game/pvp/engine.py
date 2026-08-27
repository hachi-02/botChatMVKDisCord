import random

from config import PVP_ENERGY_MAX, PVP_MAX_ROUND

from .cards import ELEMENT_ADVANTAGE, ELEM_STRONG, ELEM_WEAK


class Fighter:
    def __init__(self, card: dict):
        self.key = card["key"]
        self.name = card["name"]
        self.url = card["url"]
        self.rarity = card["rarity"]
        self.role = card["role"]
        self.element = card["element"]
        self.atk = card["atk"]
        self.max_hp = card["hp"]
        self.hp = card["hp"]
        self.spd = card["spd"]
        self.crit_rate = card["crit_rate"]
        self.crit_dmg = card["crit_dmg"]
        self.skill = card["skill"]
        self.ultimate = card["ultimate"]
        self.energy = 0
        self.atk_buff = 0.0
        self.def_debuff = 0.0
        self.shield = 0.0
        self.stunned = False

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


def _front(team):
    for f in team:
        if f.alive:
            return f
    return None


def _compute_damage(attacker: Fighter, defender: Fighter, mult: float):
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
    return dmg, crit


def _apply_effect(caster: Fighter, team: list, enemy: list, eff: dict, log: list):
    t = eff["type"]
    p = eff.get("power", 0)
    p2 = eff.get("power2", 0)
    tag = f"🔮 **{caster.name}** → **{eff['name']}**"
    if t == "ST_DMG":
        target = _front(enemy)
        if target:
            dmg, crit = _compute_damage(caster, target, p)
            log.append(f"{tag}: {target.name} mất {dmg} HP{' 💥' if crit else ''}")
    elif t == "AOE_DMG":
        for e in enemy:
            if e.alive:
                dmg, crit = _compute_damage(caster, e, p)
                log.append(f"{tag}: {e.name} -{dmg} HP{' 💥' if crit else ''}")
    elif t == "SHIELD_TEAM":
        for ally in team:
            ally.shield = max(ally.shield, p)
        log.append(f"{tag}: toàn đội giáp giảm {int(p*100)}% 🛡️")
    elif t == "HEAL":
        target = min((f for f in team if f.alive), key=lambda f: f.hp / f.max_hp)
        before = target.hp
        target.hp = min(target.max_hp, target.hp + p)
        log.append(f"{tag}: hồi {target.hp - before} HP cho {target.name} 💚")
    elif t == "BUFF_ATK":
        for ally in team:
            ally.atk_buff += p
        log.append(f"{tag}: toàn đội +{int(p*100)}% ATK ⬆️")
    elif t == "BUFF_SPD":
        for ally in team:
            ally.spd += p
        log.append(f"{tag}: toàn đội +{p} tốc độ 💨")
    elif t == "DEBUFF_DEF":
        for e in enemy:
            e.def_debuff += p
        log.append(f"{tag}: địch nhận +{int(p*100)}% sát thương 🔻")
    elif t == "STUN":
        target = _front(enemy)
        if target:
            target.stunned = True
            log.append(f"{tag}: {target.name} bị choáng ⭐")
    elif t == "SHIELD_HEAL":
        for ally in team:
            ally.shield = max(ally.shield, p)
        low = min((f for f in team if f.alive), key=lambda f: f.hp / f.max_hp)
        before = low.hp
        low.hp = min(low.max_hp, low.hp + p2)
        log.append(f"{tag}: giáp {int(p*100)}% + hồi {low.hp - before} HP cho {low.name} 🛡️💚")
    elif t == "HEAL_ST_DMG":
        low = min((f for f in team if f.alive), key=lambda f: f.hp / f.max_hp)
        before = low.hp
        low.hp = min(low.max_hp, low.hp + p)
        log.append(f"{tag}: hồi {low.hp - before} HP cho {low.name} 💚")
        target = _front(enemy)
        if target:
            dmg, crit = _compute_damage(caster, target, p2)
            log.append(f"{tag}: {target.name} -{dmg} HP{' 💥' if crit else ''}")
    elif t == "HEAL_BUFF":
        low = min((f for f in team if f.alive), key=lambda f: f.hp / f.max_hp)
        before = low.hp
        low.hp = min(low.max_hp, low.hp + p)
        for ally in team:
            ally.atk_buff += p2
        log.append(f"{tag}: hồi {low.hp - before} HP + toàn đội +{int(p2*100)}% ATK 💚⬆️")


def _basic_attack(attacker: Fighter, enemy_team: list, log: list):
    defender = _front(enemy_team)
    if defender is None:
        return
    dmg, crit = _compute_damage(attacker, defender, 1.0)
    log.append(
        f"➡️ {attacker.name} đánh thường {defender.name}: -{dmg} HP"
        f"{' 💥 CRIT!' if crit else ''}"
    )
    attacker.gain_energy(20)


def use_skill(attacker: Fighter, team: list, enemy: list, log: list):
    _apply_effect(attacker, team, enemy, attacker.skill, log)
    attacker.gain_energy(30)


def use_ultimate(attacker: Fighter, team: list, enemy: list, log: list):
    _apply_effect(attacker, team, enemy, attacker.ultimate, log)
    attacker.energy = 0


# ===================== BATTLE SESSION =====================
class BattleSession:
    def __init__(self, a_cards, b_cards, a_user, b_user, channel, bot):
        self.team_a = [Fighter(c) for c in a_cards]
        self.team_b = [Fighter(c) for c in b_cards]
        self.a_user = a_user
        self.b_user = b_user
        self.channel = channel
        self.bot = bot
        self.round = 0
        self.log = []
        self.order = []
        self.idx = 0
        self.message = None
        self.done = False

    def _enemy_of(self, fighter: Fighter):
        return self.team_b if fighter in self.team_a else self.team_a

    def _team_of(self, fighter: Fighter):
        return self.team_a if fighter in self.team_a else self.team_b

    def _owner(self, fighter: Fighter):
        return self.a_user if fighter in self.team_a else self.b_user

    def build_order(self):
        self.round += 1
        alive = [f for f in self.team_a + self.team_b if f.alive]
        alive.sort(key=lambda f: f.spd, reverse=True)
        self.order = alive
        self.idx = 0
        for team in (self.team_a, self.team_b):
            if any(f.alive and f.role == "SUP" for f in team):
                cands = [f for f in team if f.alive]
                if cands:
                    low = min(cands, key=lambda f: f.hp / f.max_hp)
                    low.hp = min(low.max_hp, low.hp + 5)

    def current_actor(self):
        while self.idx < len(self.order) and not self.order[self.idx].alive:
            self.idx += 1
        if self.idx >= len(self.order):
            if self.round >= PVP_MAX_ROUND:
                return None
            self.build_order()
        while self.idx < len(self.order) and not self.order[self.idx].alive:
            self.idx += 1
        if self.idx >= len(self.order):
            return None
        return self.order[self.idx]

    def apply_action(self, fighter: Fighter, action: str):
        team = self._team_of(fighter)
        enemy = self._enemy_of(fighter)
        if action == "normal":
            _basic_attack(fighter, enemy, self.log)
        elif action == "skill":
            use_skill(fighter, team, enemy, self.log)
        elif action == "ultimate":
            use_ultimate(fighter, team, enemy, self.log)
        self.idx += 1

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
