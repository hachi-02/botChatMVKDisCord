from config import MAX_HISTORY

chat_history = {}
user_names = {}


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


def remember_user(user_id: int, name: str):
    user_names[user_id] = name


def get_known_users() -> str:
    if not user_names:
        return ""
    lines = [f"- {name}" for name in user_names.values()]
    return "Các em đã gặp trước đó: " + ", ".join(user_names.values())
