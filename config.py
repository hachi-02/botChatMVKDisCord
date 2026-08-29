import os

from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

ROLE_ID = 1541912537744936983

MODEL_NAME = "qwen/qwen3.8-27b"

MAX_HISTORY = 10

KEYWORDS = [
    "chị cá",
    "chicá",
    "chị ca",
    "cá ơi",
    "ca ơi",
    "ê chị cá",
    "chị cá ơi",
]

CHUI_KEYWORDS = ["chửi"]

PROVOCATION_KEYWORDS = [
    "ngu", "đần", "câm", "đồ ngu", "mày ngu",
    "bạn ngu", "dở", "kém", "tệ", "loser",
    "đồ khùng", "đồ điên", "bẩn", "xấu",
]

SEARCH_KEYWORDS = [
    "tìm", "tra cứu", "thông tin", "là ai", "giới thiệu",
    "bao nhiêu", "khi nào", "ở đâu", "tại sao", "thế nào",
    "có thật", "đúng không", "so sánh", "phân biệt",
]

PROACTIVE_CHANCE = 0.2
MIN_MESSAGE_LENGTH = 10
PROACTIVE_KEYWORDS = [
    "game", "anime", "phim", "nhạc", "bài hát",
    "đồ ăn", "món ăn", "nấu", "ăn",
    "thể thao", "bóng đá", "cầu thủ",
    "học", "bài tập", "thi", "điểm",
    "tinder", "love", "crush", "tình yêu",
]

MEMBER_KEYWORDS = ["member"]

POLL_KEYWORDS = ["vote"]

REMIND_KEYWORDS = ["remind"]

EVENT_KEYWORDS = ["make event", "event"]
INVITE_KEYWORDS = ["link"]
SUMMARY_KEYWORDS = ["summary"]
SUMMARY_LIMIT = 50
SUMMARY_MAX = 500
HELP_KEYWORDS = ["menu"]
EVENT_HELP_KEYWORDS = [
    "như nào", "cách", "hướng dẫn", "làm sao", "như thế nào",
    "dùng sao", "guide", "how to", "how","chỉ"
]
EVENT_REMIND_MINUTES = 15
EVENT_DEFAULT_DURATION_MINUTES = 120

EMOJI_MAP = {
    "[MEOW]": "<:skirkmeow:1471088875106730106>",
    "[HEART]": "<:skirkheart:1471089365500559455>",
    "[SMILE]": "<:skirksmile:1471089210881478768>",
    "[ANGRY]": "<:skirkangry:1471089056975687814>",
}

DATABASE_URL = os.getenv("DATABASE_URL")

ASSET_KEYWORDS = ["bag"]
DAILY_KEYWORDS = ["daily"]
DAILY_GEMS = 10
DAILY_MORA = 500
POINT_COOLDOWN = 30
POINTS_PER_MSG = 5
GEM_PER_MSG = 10
MORA_PER_MSG = 500
POINTS_PER_LEVEL = 200

GACHA_KEYWORDS = ["gacha"]
COLLECTION_KEYWORDS = ["inventory"]
SHOW_KEYWORDS = ["show"]
INFO_KEYWORDS = ["info"]

VOICE_IN_KEYWORDS = ["voice in", "voicein"]
VOICE_OUT_KEYWORDS = ["voice out", "voiceout"]

PVP_KEYWORDS = ["pvp"]
PVP_RANK_KEYWORDS = ["point", "top"]
PVP_TEAM_SIZE = 3
PVP_MAX_ROUND = 30
PVP_K = 32
PVP_START_RATING = 1000
PVP_ACCEPT_TIMEOUT = 60
PVP_TURN_TIMEOUT = 60
PVP_ENERGY_MAX = 100
PVP_SP_START = 3
PVP_SP_MAX = 5
PVP_DODGE_FACTOR = 0.15
PVP_DODGE_CAP = 0.30
PVP_BATTLE_ANIM_GIF = "https://res.cloudinary.com/z2ffqaaf/image/upload/v1787884964/giphy_felw8m.gif"
PVP_CHALLENGE_GIF = "https://res.cloudinary.com/z2ffqaaf/image/upload/v1787884708/giphy_l5i3pz.gif"

CHAR_MAX_LEVEL = 90
LEVEL_COST_PER = 500
LEVEL_HP_BONUS = 10
LEVEL_ATK_BONUS = 2
LEVEL_SPD_BONUS = 0.2

IDLE_HOURS = 4.5
IDLE_CHECK_INTERVAL = 60
IDLE_MAX_PER_DAY = 2
IDLE_SCAN_LIMIT = 200
IDLE_CHANNEL_NAMES = ["chat-chit"]

REPORT_WEEKDAY = 6          # Chủ nhật (Monday=0)
REPORT_HOUR = 20
REPORT_MINUTE = 0
REPORT_CHANNEL_NAMES = ["chat-chit"]
REPORT_CHECK_INTERVAL = 60
REPORT_KEEP_DAYS = 30

HUG_GIFS = [
    "https://res.cloudinary.com/z2ffqaaf/image/upload/v1788011690/giphy_dueiol.webp",
    "https://res.cloudinary.com/z2ffqaaf/image/upload/v1788011662/200_d8iav6.webp",
    "https://res.cloudinary.com/z2ffqaaf/image/upload/v1788011652/giphy_eldxvm.webp",
    "https://res.cloudinary.com/z2ffqaaf/image/upload/v1788011638/giphy_i3k8aa.webp",
]