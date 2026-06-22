from collections.abc import Awaitable, Callable


class WorkModeController:
    def __init__(self, clear_runtime: Callable[[], Awaitable[None]] | None = None):
        self.is_working = True
        self._clear_runtime = clear_runtime

    async def handle_command(self, text: str) -> str | None:
        command = str(text or "").strip()
        if command == "状态":
            return f"当前状态：{'上班' if self.is_working else '下班'}"
        if command == "下班":
            self.is_working = False
            if self._clear_runtime is not None:
                await self._clear_runtime()
            return "已切换：下班"
        if command == "上班":
            self.is_working = True
            return "已切换：上班"
        return None
