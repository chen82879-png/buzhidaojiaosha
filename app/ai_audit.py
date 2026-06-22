import asyncio
import json
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta

from app.alert_rules import is_ignored_customer_text


LOOKBACK_HOURS = {"off_duty": 10, "ordinary": 12, "full": 20}
EXCLUDED_CHAT_IDS = {"-1002807120955", "-1002169616907"}


@dataclass(frozen=True)
class GeminiDecision:
    needs_review: bool
    reason: str


def parse_gemini_decision(raw: str) -> GeminiDecision:
    text = str(raw or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1]).strip()
    try:
        payload = json.loads(text)
        value = payload.get("needs_review")
        reason = str(payload.get("reason") or "").strip()
        if not isinstance(value, bool) or not reason:
            raise ValueError("invalid decision")
        return GeminiDecision(needs_review=value, reason=reason)
    except (TypeError, ValueError, json.JSONDecodeError):
        return GeminiDecision(needs_review=True, reason="模型结果异常，需人工复核")


class GeminiClient:
    def __init__(self, api_key: str, model: str = "gemini-3.5-flash", timeout: int = 20):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    async def decide(self, prompt: str) -> GeminiDecision:
        if not self.api_key:
            return GeminiDecision(True, "Gemini 未配置，需人工复核")
        try:
            raw = await asyncio.wait_for(asyncio.to_thread(self._request, prompt), self.timeout + 1)
            return parse_gemini_decision(raw)
        except Exception:
            return GeminiDecision(True, "Gemini 调用失败，需人工复核")

    def _request(self, prompt: str) -> str:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
            f"?key={self.api_key}"
        )
        body = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode("utf-8")
        request = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return payload["candidates"][0]["content"]["parts"][0]["text"]


class HistoricalAuditor:
    def __init__(self, repo, client: GeminiClient):
        self.repo = repo
        self.client = client

    async def run(self, mode: str, now: datetime) -> dict:
        if mode not in LOOKBACK_HOURS:
            raise ValueError("unsupported audit mode")
        since = now - timedelta(hours=LOOKBACK_HOURS[mode])
        messages = self.repo.list_message_snapshots_since(since, exclude_chat_ids=EXCLUDED_CHAT_IDS)
        replies = {(item.chat_id, item.reply_to_message_id) for item in messages if item.is_staff}
        candidates = [
            item for item in messages
            if not item.is_staff
            and item.chat_id not in EXCLUDED_CHAT_IDS
            and (item.chat_id, item.message_id) not in replies
            and item.message_kind not in {"sticker", "gif"}
            and not is_ignored_customer_text(item.text)
        ][-100:]

        async def inspect(item):
            context = [candidate for candidate in messages if candidate.chat_id == item.chat_id]
            prompt = self._prompt(item, context[-12:])
            decision = await self.client.decide(prompt)
            if decision.needs_review:
                return {
                    "chat_id": item.chat_id,
                    "message_id": item.message_id,
                    "text": item.text[:200],
                    **asdict(decision),
                }
            return None

        inspected = await asyncio.gather(*(inspect(item) for item in candidates))
        findings = [item for item in inspected if item is not None]
        return {
            "mode": mode,
            "lookback_hours": LOOKBACK_HOURS[mode],
            "scanned": len(messages),
            "findings": findings,
            "generated_at": now.isoformat(),
        }

    @staticmethod
    def _prompt(message, context) -> str:
        transcript = "\n".join(
            f"{'客服' if row.is_staff else '客户'} #{row.message_id}: {row.text}" for row in context
        )
        return (
            "判断目标客户消息是否仍需要客服回复。只返回 JSON："
            '{"needs_review": true或false, "reason": "简短原因"}。'
            "明确引用闭环、贴纸/GIF、白名单或领导明确同意可判 false；不确定必须 true。\n"
            f"目标消息 #{message.message_id}: {message.text}\n上下文：\n{transcript}"
        )
