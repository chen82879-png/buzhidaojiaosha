def build_message_url(chat_id: str, message_id: int, username: str = "") -> str:
    if username:
        return f"https://t.me/{username}/{message_id}"
    internal_id = chat_id
    if internal_id.startswith("-100"):
        internal_id = internal_id[4:]
    elif internal_id.startswith("-"):
        internal_id = internal_id[1:]
    return f"https://t.me/c/{internal_id}/{message_id}"
