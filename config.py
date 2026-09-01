import os

from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

ROLE_ID = 1541912537744936983

MODEL_NAME = "qwen/qwen3.8-27b"

MAX_HISTORY = 15

KEYWORDS = [
    "chị đại",
    "chịdại",
    "đại ơi",
    "ê chị đại",
    "chị đại ơi",
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

HUG_GIFS = [
    "https://res.cloudinary.com/z2ffqaaf/image/upload/v1788011690/giphy_dueiol.webp",
    "https://res.cloudinary.com/z2ffqaaf/image/upload/v1788011662/200_d8iav6.webp",
    "https://res.cloudinary.com/z2ffqaaf/image/upload/v1788011652/giphy_eldxvm.webp",
    "https://res.cloudinary.com/z2ffqaaf/image/upload/v1788011638/giphy_i3k8aa.webp",
]