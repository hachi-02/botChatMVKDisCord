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