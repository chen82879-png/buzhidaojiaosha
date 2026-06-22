WAIT_TIMEOUT_MINUTES = 12
SEVERE_WAIT_DELAY_MINUTES = 10
SEVERE_WAIT_TOTAL_MINUTES = WAIT_TIMEOUT_MINUTES + SEVERE_WAIT_DELAY_MINUTES
FOLLOWUP_TIMEOUT_MINUTES = 15
REPLY_TIMEOUT_MINUTES = 5
SELF_REPLY_TIMEOUT_MINUTES = 3

IGNORE_WORDS = {
    "好", "1", "不用了", "到了", "好的", "谢谢", "收到", "明白", "好的谢谢",
    "ok", "好滴", "好的呢", "嗯", "嗯嗯", "谢了", "okk", "k", "行", "妥",
    "了解", "已收", "没问题", "好的收到", "ok了", "麻烦了", "好的感谢", "哦",
    "知道了", "好的知道了", "没事了",
}


def normalize_rule_text(text: str) -> str:
    return "".join(str(text or "").lower().split()).strip("。.!！?？,，、")


def is_ignored_customer_text(text: str, words=IGNORE_WORDS) -> bool:
    normalized = normalize_rule_text(text)
    return normalized in {normalize_rule_text(word) for word in words}


def is_followup_keyword(text: str, keywords) -> bool:
    normalized = str(text or "").strip()
    return normalized in {str(keyword).strip() for keyword in keywords if str(keyword).strip()}
