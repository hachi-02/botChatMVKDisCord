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
    "chica",
    "chicá",
    "chị ca",
    "cá ơi",
    "ca ơi",
    "ê chị cá",
    "ê chica",
    "chị cá ơi",
    "chica ơi",
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

MEMBER_KEYWORDS = [
    "danh sách thành viên", "ai trong group", "có ai", "thành viên",
    "list member", "ai đang online", "bao nhiêu người", "ai đang ở đây",
]

POLL_KEYWORDS = ["poll", "vote", "bầu", "bỏ phiếu"]

REMIND_KEYWORDS = ["nhắc t", "remind", "nhắc tôi", "nhắc em"]

EVENT_KEYWORDS = ["tạo sự kiện", "tạo event", "lên lịch", "event", "schedule"]
INVITE_KEYWORDS = ["lời mời", "link mời"]
SUMMARY_KEYWORDS = ["tóm tắt"]
SUMMARY_LIMIT = 50
SUMMARY_MAX = 500
HELP_KEYWORDS = ["menu", "help"]
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

ASSET_KEYWORDS = ["tài sản", "tai san", "assets", "nguyên thạch", "mora"]
DAILY_KEYWORDS = ["daily"]
DAILY_GEMS = 10
DAILY_MORA = 500
POINT_COOLDOWN = 30
POINTS_PER_MSG = 5
GEM_PER_MSG = 10
MORA_PER_MSG = 500
POINTS_PER_LEVEL = 200

GACHA_KEYWORDS = ["gacha", "quay", "roll"]
COLLECTION_KEYWORDS = ["sở hữu", "collection", "kho", "bộ sưu tập"]
SHOW_KEYWORDS = ["show", "xem ảnh", "ảnh"]

PVP_KEYWORDS = ["pvp", "pk", "thách đấu"]
PVP_RANK_KEYWORDS = ["điểm", "top"]
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