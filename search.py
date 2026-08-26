from ddgs import DDGS


def search_web(query: str, max_results: int = 3) -> str:
    try:
        results = DDGS().text(query, max_results=max_results)

        if not results:
            return "Không tìm thấy kết quả."

        output = ""
        for i, r in enumerate(results, 1):
            title = r.get("title", "")
            body = r.get("body", "")
            href = r.get("href", "")
            output += f"{i}. **{title}**\n{body}\n{href}\n\n"

        return output.strip()

    except Exception as e:
        return f"Lỗi tìm kiếm: {e}"
