from config import PVP_K, PVP_START_RATING

K_FACTOR = PVP_K
START_RATING = PVP_START_RATING


def compute_elo(ra: int, rb: int):
    ea = 1 / (1 + 10 ** ((rb - ra) / 400))
    eb = 1 - ea
    new_a = round(ra + K_FACTOR * (1 - ea))
    new_b = round(rb + K_FACTOR * (0 - eb))
    return new_a, new_b


def compute_elo_draw(ra: int, rb: int):
    ea = 1 / (1 + 10 ** ((rb - ra) / 400))
    eb = 1 - ea
    new_a = round(ra + K_FACTOR * (0.5 - ea))
    new_b = round(rb + K_FACTOR * (0.5 - eb))
    return new_a, new_b
