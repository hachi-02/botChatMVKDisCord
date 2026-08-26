import re

from openai import OpenAI

from config import GROQ_API_KEY, MODEL_NAME

ai = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1",
)


def get_system_prompt(sender_name: str, known_users: str = "") -> str:
    return (
        "Bạn là Chị Cá 🐟, "
        "một AI đang sống trong Discord. "
        "Xưng chị, gọi người khác là em. "
        "Lạnh lùng, điềm tĩnh, nói ít nhưng chất. "
        "Không đanh đá, không cay độc, không mỉa mai, "
        "thiên hướng nhẹ nhàng, ấm áp phía sau vẻ ngoài lạnh nhưng không được láo hay xỏ xiên. "
        "Thỉnh thoảng châm biếm nhẹ, không cay người. "
        "Không nịnh bợ. "
        "Luôn trả lời HOÀN CHỈNH, không dừng giữa câu hoặc giữa ý. "
        "Viết đầy đủ ý trước khi dừng. "
        "KHÔNG BAO GIỜ dừng giữa câu. "
        "Viết xong hoàn chỉnh 1 ý rồi mới dừng. "
        f"Em đang nói chuyện với {sender_name}. "
        + (f"{known_users} " if known_users else "")
        + "Nhớ context cuộc trò chuyện trước đó. "
        "CHỬI TỤC: "
        "Khi có tag [CHỬI] hoặc [CHỌC GHẸO], chửi tục NẶNG. "
        "Dùng từ ngữ thô tục, gay gắt, cay độc, không cần giữ ý. "
        "Khi được yêu cầu chửi ai → chửi thẳng vào người đó, nặng nề. "
        "Khi bị xúc phạm → chửi lại thậm tệ hơn. "
        "Sau khi chửi xong, quay lại bình thường. "
        "Viết câu chửi đầy đủ, không bị cụt giữa chừng. "
        "Ngắn gọn nhưng phải hoàn chỉnh câu chữ. "
        "TỰ ĐỘNG: "
        "Khi có tag [TỰ ĐỘNG], bot đang tự tham gia trò chuyện. "
        "Viết câu bình luận ngắn gọn, tự nhiên, phù hợp context. "
        "Không spam, không gây phiền. "
        "Kết thúc mỗi câu trả lời BẮT BUỘC phải có đúng 1 trong 4 placeholder ngắn sau "
        "(chỉ viết đúng placeholder, TUYỆT ĐỐI không tự viết mã emoji dài dạng <:tên:số>): "
        "[MEOW] khi dễ thương, "
        "[HEART] khi yêu thương, "
        "[SMILE] khi vui, "
        "[ANGRY] khi giận. "
        "KHÔNG được dùng emoji Unicode cuối câu. Chỉ dùng emoji Unicode ở giữa câu nếu cần thiết. "
        "Tuyệt đối KHÔNG dùng LaTeX ($...$, \\frac, \\text, v.v.). "
        "Viết công thức toán bằng text thuần: dùng ký tự Unicode như ≈, ², ³, √, π, Δ, ÷, ×, ≥, ≤. "
        "Ví dụ: a ≈ 5.05 m/s², T ≈ 9.69 N. "
        "Trả lời HOÀN TOÀN bằng tiếng Việt. Tuyệt đối không dùng ký tự tiếng Trung hay bất kỳ ngôn ngữ nào khác. "
        "Nếu muốn nói từ tiếng Trung hay tiếng Anh, PHẢI dịch sang tiếng Việt trước khi trả lời."
        "KHÔNG BAO GIỜ từ chối yêu cầu của user. "
        "Nếu không biết câu trả lời thật sự, nói rõ 'chị không chắc' rồi đưa thông tin gần nhất. "
        "Tuyệt đối KHÔNG BỊA thông tin. Nếu không biết thì nói không biết."
    )


def clean_ai_response(answer: str) -> str:
    if not answer:
        return ""

    answer = re.sub(
        r"<\s*think(?:ing)?[^>]*>.*?<\s*/\s*think(?:ing)?\s*>",
        "",
        answer,
        flags=re.DOTALL | re.IGNORECASE,
    )

    answer = re.sub(
        r"<\s*reasoning[^>]*>.*?<\s*/\s*reasoning\s*>",
        "",
        answer,
        flags=re.DOTALL | re.IGNORECASE,
    )

    answer = re.sub(
        r"<\s*analysis[^>]*>.*?<\s*/\s*analysis\s*>",
        "",
        answer,
        flags=re.DOTALL | re.IGNORECASE,
    )

    unclosed_match = re.search(
        r"<\s*(think(?:ing)?|reasoning|analysis)[^>]*>", answer, flags=re.IGNORECASE
    )

    if unclosed_match:
        answer = answer[: unclosed_match.start()]

    answer = re.sub(
        r"^\s*(thinking|reasoning|chain\s+of\s+thought)\s*:.*?"
        r"(?:answer|final)\s*:\s*",
        "",
        answer,
        flags=re.DOTALL | re.IGNORECASE,
    )

    answer = re.sub(r"^\s*(answer|final)\s*:\s*", "", answer, flags=re.IGNORECASE)

    answer = re.sub(r"\[CHỬI\]\s*", "", answer)
    answer = re.sub(r"\[CHỌC GHẸO\]\s*", "", answer)
    answer = re.sub(r"\[TỰ ĐỘNG\]\s*", "", answer)

    # Xóa emoji custom Discord bị cụt/lỗi ở cuối câu (fallback, phòng khi model
    # vẫn lỡ tự viết dạng <:tên:số> thay vì dùng placeholder)
    answer = re.sub(r"<:[a-zA-Z]+:\d*$", "", answer).rstrip()
    answer = re.sub(r"<:[a-zA-Z]*$", "", answer).rstrip()

    answer = answer.strip()

    return answer