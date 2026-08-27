import random

from config import PVP_MAX_ROUND

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
        self.energy = 0
        self.atk_buff = 0.0
        self.def_debuff = 0.0
        self.shield = 0.0
        self.stunned = False

    @property
    def alive(self) -> bool:
        return self.hp > 0


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
    crit = random.random() < attacker.crit_rate
    if crit:
        base *= attacker.crit_dmg
    dmg = max(1, round(base))
    reduction = defender.shield + (0.15 if defender.role == "TANK" else 0.0)
    dmg = max(1, round(dmg * (1 - min(reduction, 0.6))))
    dmg = round(dmg * (1 + defender.def_debuff))
    return max(1, dmg), crit


def _apply_skill(caster: Fighter, team: list, enemy: list, log: list):
    s = caster.skill
    t = s["type"]
    p = s["power"]
    tag = f"🔮 **{caster.name}** thi triển **{s['name']}**"
    if t == "ST_DMG":
        target = _front(enemy)
        if target:
            dmg, crit = _compute_damage(caster, target, p)
            target.hp -= dmg
            log.append(f"{tag}: gây {dmg} sát thương lên {target.name}{' 💥' if crit else ''}")
    elif t == "AOE_DMG":
        for e in enemy:
            if e.alive:
                dmg, crit = _compute_damage(caster, e, p)
                e.hp -= dmg
                log.append(f"{tag}: {e.name} mất {dmg} HP{' 💥' if crit else ''}")
    elif t == "SHIELD_TEAM":
        for ally in team:
            ally.shield = max(ally.shield, p)
        log.append(f"{tag}: toàn đội được giáp giảm {int(p*100)}% sát thương 🛡️")
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
            log.append(f"{tag}: {target.name} bị choáng, mất lượt ⭐")


def resolve_battle(team_a_cards: list, team_b_cards: list):
    ta = [Fighter(c) for c in team_a_cards]
    tb = [Fighter(c) for c in team_b_cards]
    log = []

    for rnd in range(1, PVP_MAX_ROUND + 1):
        for f in ta + tb:
            f.shield = 0.0

        # phase 1: năng lượng + skill
        for team, enemy in ((ta, tb), (tb, ta)):
            for f in team:
                if not f.alive:
                    continue
                f.energy += 1
                if f.energy >= f.skill["cost"]:
                    _apply_skill(f, team, enemy, log)
                    f.energy = 0

        # phase 2: đòn thường của tiền tuyến
        fa, fb = _front(ta), _front(tb)
        if fa and fb:
            order = [fa, fb] if fa.spd >= fb.spd else [fb, fa]
            for attacker in order:
                if not attacker.alive:
                    continue
                enemy_team = tb if attacker in ta else ta
                defender = _front(enemy_team)
                if defender is None:
                    break
                if attacker.stunned:
                    attacker.stunned = False
                    log.append(f"⭐ {attacker.name} bị choáng, bỏ lượt")
                    continue
                dmg, crit = _compute_damage(attacker, defender, 1.0)
                defender.hp -= dmg
                log.append(
                    f"➡️ {attacker.name} đánh {defender.name}: -{dmg} HP"
                    f"{' 💥 CRIT!' if crit else ''}"
                )

        if not any(f.alive for f in ta):
            return {"winner": "B", "log": log, "team_a": ta, "team_b": tb}
        if not any(f.alive for f in tb):
            return {"winner": "A", "log": log, "team_a": ta, "team_b": tb}

    return {"winner": None, "log": log, "team_a": ta, "team_b": tb}
