from app.models import PendingMessage, RuleStaff


def render_timeout_alert(
    staff: RuleStaff,
    pending: PendingMessage,
    timeout_minutes: int,
    private_message_status: str = "",
) -> str:
    username = f"@{staff.telegram_username}" if staff.telegram_username else ""
    keywords = "、".join(pending.matched_keywords)
    status_map = {
        "wait": f"稍等任务 {timeout_minutes} 分钟无引用回复",
        "followup": f"跟进任务 {timeout_minutes} 分钟无引用回复",
        "reply": f"漏回任务 {timeout_minutes} 分钟无客服回复",
        "self_reply": f"自回任务 {timeout_minutes} 分钟无客服处理",
    }
    reason_map = {
        "wait": "客服发送稍等后，后续未发现有效引用回复",
        "followup": "客户再次引用已完成稍等消息后，未发现客服跟进",
        "reply": "客户引用客服消息咨询后，未发现客服继续处理",
        "self_reply": "客户在待处理链路中追加消息后，未发现客服处理",
    }
    status = status_map.get(pending.task_type, f"任务 {timeout_minutes} 分钟未处理")
    reason = reason_map.get(pending.task_type, "任务超时未处理")
    return "\n".join(
        [
            f"接收人员：{staff.display_name}{private_message_status} ({username})",
            f"关键词：{keywords}",
            f"群组：{pending.chat_name or pending.chat_id}",
            f"客服：{keywords}",
            f"时间：{pending.message_time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"状态：{status}",
            f"原因：{reason}",
            "原消息链接：打开原消息",
            pending.message_url,
        ]
    )


def render_severe_timeout_alert(
    staff: RuleStaff,
    pending: PendingMessage,
    overdue_minutes: int,
) -> str:
    username = f"@{staff.telegram_username}" if staff.telegram_username else ""
    keywords = "、".join(pending.matched_keywords)
    return "\n".join(
        [
            "严重超时预警",
            f"接收人员：{staff.display_name} ({username})",
            f"关键词：{keywords}",
            f"群组：{pending.chat_name or pending.chat_id}",
            f"状态：首次预警后 {overdue_minutes} 分钟仍未闭环",
            "原消息链接：打开原消息",
            pending.message_url,
        ]
    )


class TelegramAlertSender:
    def __init__(self, bot):
        self.bot = bot

    async def send_timeout_alert(
        self,
        staff: RuleStaff,
        pending: PendingMessage,
        timeout_minutes: int,
    ) -> dict[str, str]:
        text = render_timeout_alert(staff, pending, timeout_minutes)
        try:
            await self.bot.send_message(chat_id=staff.telegram_user_id, text=text)
            return {"status": "sent", "error_message": ""}
        except Exception as exc:
            return {"status": "failed", "error_message": str(exc)}

    async def send_severe_timeout_alert(
        self,
        staff: RuleStaff,
        pending: PendingMessage,
        overdue_minutes: int,
    ) -> dict[str, str]:
        text = render_severe_timeout_alert(staff, pending, overdue_minutes)
        try:
            await self.bot.send_message(chat_id=staff.telegram_user_id, text=text)
            return {"status": "sent", "error_message": ""}
        except Exception as exc:
            return {"status": "failed", "error_message": str(exc)}
