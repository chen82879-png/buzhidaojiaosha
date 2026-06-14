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


def normalize_ignore_text(text: str) -> str:
    return "".join(str(text or "").lower().split()).strip("。.!！?？,，、")


def is_ignored_followup_text(text: str, ignore_words: set[str] | None = None) -> bool:
    words = ignore_words or DEFAULT_IGNORE_WORDS
    normalized = normalize_ignore_text(text)
    return normalized in {normalize_ignore_text(word) for word in words}
