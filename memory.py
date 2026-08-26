from config import MAX_HISTORY

chat_history = {}


def add_message(channel_id: int, role: str, content: str):
    if role == "assistant" and len(content) > 500:
        content = content[:500] + "..."

    if channel_id not in chat_history:
        chat_history[channel_id] = []

    chat_history[channel_id].append({
        "role": role,
        "content": content,
    })

    if len(chat_history[channel_id]) > MAX_HISTORY:
        chat_history[channel_id] = chat_history[channel_id][-MAX_HISTORY:]


def get_history(channel_id: int) -> list:
    return chat_history.get(channel_id, [])
