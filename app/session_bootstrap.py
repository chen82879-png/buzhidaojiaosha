import base64
from pathlib import Path


def restore_session_from_env(session_path: str, encoded_session: str) -> bool:
    if not encoded_session:
        return False
    path = Path(session_path)
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(base64.b64decode(encoded_session))
    return True
