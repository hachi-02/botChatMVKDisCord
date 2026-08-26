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
    "chửi",
]

CHUI_KEYWORDS = ["chửi"]

PROVOCATION_KEYWORDS = [
    "ngu", "đần", "câm", "đồ ngu", "mày ngu",
    "bạn ngu", "dở", "kém", "tệ", "loser",
    "đồ khùng", "đồ điên", "bẩn", "xấu",
]
