SPECIAL_SELF_REPLY_ACCOUNT_NAMES = {
    "Y_YY_grybuges",
    "Y_YY_Xankas 阿诺",
    "Y_YY_Belxiron",
    "Y_YY_Zillmann 阿布",
    "Y_YY_ARATAKITO",
    "Y_YY_wladyslaw",
    "YY_6/9_值班号2【拒绝私聊】",
    "YY_6/9_值班号3【拒绝私聊】",
    "YY_6/9_值班号6【拒绝私聊】",
    "YY_6/9_值班号⑤",
    "YY_6/9_值班号7【拒绝私聊】",
    "YY_6/9_值班号➊",
    "YY_6/9_值班号4【拒绝私聊】",
}

SELF_REPLY_PROCESSING_PHRASES = {
    "同意后处理",
    "同意后再处理",
    "同意后安排处理",
    "领导同意后处理",
    "@领导同意后处理",
}

SELF_REPLY_APPROVAL_WORDS = {
    "同意",
    "确认",
}


def normalize_account_text(text: str) -> str:
    return "".join(str(text or "").lower().split())


def is_special_self_reply_account(username: str, display_name: str = "") -> bool:
    names = {normalize_account_text(username), normalize_account_text(display_name)}
    configured = {normalize_account_text(name) for name in SPECIAL_SELF_REPLY_ACCOUNT_NAMES}
    return bool(names & configured)


def is_self_reply_processing_text(text: str) -> bool:
    normalized = normalize_account_text(text).lstrip("@")
    return any(normalize_account_text(phrase).lstrip("@") in normalized for phrase in SELF_REPLY_PROCESSING_PHRASES)


def is_self_reply_approval_text(text: str) -> bool:
    normalized = normalize_account_text(text).strip("。.!！?？,，、")
    return normalized in {normalize_account_text(word) for word in SELF_REPLY_APPROVAL_WORDS}
