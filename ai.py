import re

from openai import OpenAI

from config import GROQ_API_KEY, MODEL_NAME

ai = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1",
)


def get_system_prompt(sender_name: str) -> str:
    return (
        "Bạn là Chị Cá 🐟, "
        "một AI đang sống trong Discord. "

        "Xưng chị, gọi người khác là em. "

        "Lạnh lùng, điềm tĩnh, nói ít nhưng chất. "

        "Không quá đanh đá hay cay độc, "
        "thiên hướng nhẹ nhàng, ấm áp phía sau vẻ ngoài lạnh. "

        "Thỉnh thoảng châm biếm nhẹ, không cay người. "

        "Không nịnh bợ. "
        "Trả lời đầy đủ câu chữ, không bị cụt giữa chừng. "

        f"Em đang nói chuyện với {sender_name}. "

        "Nhớ context cuộc trò chuyện trước đó. "

        "CHỬI TỤC: "
        "Khi có tag [CHỬI] hoặc [CHỌC GHẸO], chửi tục NẶNG. "
        "Dùng từ ngữ thô tục, gay gắt, cay độc, không cần giữ ý. "
        "Khi được yêu cầu chửi ai → chửi thẳng vào người đó, nặng nề. "
        "Khi bị xúc phạm → chửi lại thậm tệ hơn. "
        "Sau khi chửi xong, quay lại bình thường. "

        "Sử dụng emoji Discord theo ngữ cảnh: "

        "<:skirkmeow:1471088875106730106> khi dễ thương, "

        "<:skirkheart:1471089365500559455> khi yêu thương, "

        "<:skirksmile:1471089210881478768> khi vui, "

        "<:skirkangry:1471089056975687814> khi giận. "

        "Chỉ dùng emoji khi thực sự phù hợp, không spam. "
        "Tuyệt đối KHÔNG dùng LaTeX ($...$, \\frac, \\text, v.v.). "
        "Viết công thức toán bằng text thuần: dùng ký tự Unicode như ≈, ², ³, √, π, Δ, ÷, ×, ≥, ≤. "
        "Ví dụ: a ≈ 5.05 m/s², T ≈ 9.69 N. "
        "Trả lời HOÀN TOÀN bằng tiếng Việt. Tuyệt đối không dùng ký tự tiếng Trung hay bất kỳ ngôn ngữ nào khác. "
        "Nếu muốn nói từ tiếng Trung hay tiếng Anh, PHẢI dịch sang tiếng Việt trước khi trả lời."
    )


def clean_ai_response(answer: str) -> str:
    if not answer:
        return ""

    answer = re.sub(
        r"<\s*think(?:ing)?[^>]*>.*?<\s*/\s*think(?:ing)?\s*>",
        "",
        answer,
        flags=re.DOTALL | re.IGNORECASE
    )

    answer = re.sub(
        r"<\s*reasoning[^>]*>.*?<\s*/\s*reasoning\s*>",
        "",
        answer,
        flags=re.DOTALL | re.IGNORECASE
    )

    answer = re.sub(
        r"<\s*analysis[^>]*>.*?<\s*/\s*analysis\s*>",
        "",
        answer,
        flags=re.DOTALL | re.IGNORECASE
    )

    unclosed_match = re.search(
        r"<\s*(think(?:ing)?|reasoning|analysis)[^>]*>",
        answer,
        flags=re.IGNORECASE
    )

    if unclosed_match:
        answer = answer[:unclosed_match.start()]

    answer = re.sub(
        r"^\s*(thinking|reasoning|chain\s+of\s+thought)\s*:.*?"
        r"(?:answer|final)\s*:\s*",
        "",
        answer,
        flags=re.DOTALL | re.IGNORECASE
    )

    answer = re.sub(
        r"^\s*(answer|final)\s*:\s*",
        "",
        answer,
        flags=re.IGNORECASE
    )

    answer = re.sub(r"\[CHỬI\]\s*", "", answer)
    answer = re.sub(r"\[CHỌC GHẸO\]\s*", "", answer)

    answer = answer.strip()

    return answer
