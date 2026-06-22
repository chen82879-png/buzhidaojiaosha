import pytest

from app.work_mode import WorkModeController


@pytest.mark.asyncio
async def test_work_mode_commands_change_state_and_clear_on_off_duty():
    cleared = []

    async def clear_runtime():
        cleared.append(True)

    mode = WorkModeController(clear_runtime=clear_runtime)

    assert await mode.handle_command("状态") == "当前状态：上班"
    assert await mode.handle_command("下班") == "已切换：下班"
    assert mode.is_working is False
    assert cleared == [True]
    assert await mode.handle_command("状态") == "当前状态：下班"
    assert await mode.handle_command("上班") == "已切换：上班"
    assert mode.is_working is True


@pytest.mark.asyncio
async def test_unknown_work_mode_command_is_ignored():
    mode = WorkModeController()
    assert await mode.handle_command("hello") is None
