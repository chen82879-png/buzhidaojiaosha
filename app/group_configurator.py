from app.fixed_keywords import FIXED_KEYWORDS
from app.monitor_groups import DEFAULT_MONITOR_GROUP_NAMES


def normalize_group_name(value: str) -> str:
    return " ".join(value.strip().casefold().split())


def upsert_monitor_group(repo, chat_id: str, chat_name: str) -> int:
    row = repo.conn.execute("SELECT id FROM monitor_rules WHERE chat_id = ?", (chat_id,)).fetchone()
    if row is None:
        rule_id = repo.create_monitor_rule(chat_id=chat_id, chat_name=chat_name, enabled=True)
    else:
        rule_id = int(row["id"])
        repo.conn.execute(
            """
            UPDATE monitor_rules
            SET chat_name = ?, enabled = 1, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (chat_name, rule_id),
        )
        repo.conn.commit()
    for keyword in FIXED_KEYWORDS:
        repo.conn.execute(
            """
            INSERT INTO rule_keywords(rule_id, keyword, enabled, note)
            VALUES (?, ?, 1, '')
            ON CONFLICT(rule_id, keyword) DO UPDATE SET
                enabled = 1,
                updated_at = CURRENT_TIMESTAMP
            """,
            (rule_id, keyword),
        )
    repo.conn.commit()
    return rule_id


async def configure_monitor_groups_from_dialogs(repo, client, group_names=None) -> dict[str, object]:
    names = group_names or DEFAULT_MONITOR_GROUP_NAMES
    wanted = {normalize_group_name(name): name for name in names}
    found: dict[str, dict[str, str]] = {}
    async for dialog in client.iter_dialogs():
        title = getattr(dialog, "name", "") or ""
        key = normalize_group_name(title)
        if key not in wanted:
            continue
        entity = dialog.entity
        chat_id = str(getattr(entity, "id", ""))
        if chat_id and not chat_id.startswith("-100"):
            chat_id = f"-100{chat_id}"
        upsert_monitor_group(repo, chat_id=chat_id, chat_name=title)
        found[wanted[key]] = {"chat_name": title, "chat_id": chat_id}
    missing = [name for name in names if name not in found]
    return {
        "requested_count": len(names),
        "configured_count": len(found),
        "configured": list(found.values()),
        "missing": missing,
    }
