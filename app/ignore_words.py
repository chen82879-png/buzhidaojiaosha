DEFAULT_IGNORE_WORDS = {
    "1",
    "d",
    "D",
    "好",
    "好的",
    "好滴",
    "好的呢",
    "收到",
    "已收",
    "明白",
    "明白了",
    "了解",
    "知道了",
    "谢谢",
    "谢谢了",
    "好的谢谢",
    "好的感谢",
    "不用了",
    "没事了",
    "没问题",
    "ok",
    "okk",
    "ok了",
    "k",
    "嗯",
    "嗯嗯",
    "哦",
    "行",
    "妥",
}

CONTINUING_STAFF_REPLY_WORDS = {
    "=",
    "1",
    "稍等",
    "请稍等",
    "核实中",
    "还没好",
    "再处理",
    "处理中",
    "还在处理",
    "正在处理",
}


def normalize_ignore_text(text: str) -> str:
    return "".join(str(text or "").lower().split()).strip("。.!！?？,，、")


def is_ignored_followup_text(text: str, ignore_words: set[str] | None = None) -> bool:
    words = ignore_words or DEFAULT_IGNORE_WORDS
    normalized = normalize_ignore_text(text)
    return normalized in {normalize_ignore_text(word) for word in words}


def is_continuing_staff_reply_text(text: str) -> bool:
    normalized = normalize_ignore_text(text)
    normalized_words = {normalize_ignore_text(word) for word in CONTINUING_STAFF_REPLY_WORDS}
    if normalized in normalized_words:
        return True
    return any(
        word in normalized
        for word in {
            normalize_ignore_text("核实中"),
            normalize_ignore_text("还没好"),
            normalize_ignore_text("再处理"),
            normalize_ignore_text("处理中"),
            normalize_ignore_text("还在处理"),
            normalize_ignore_text("正在处理"),
        }
    )
