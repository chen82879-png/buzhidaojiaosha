import base64

from app.session_bootstrap import restore_session_from_env


def test_restore_session_from_env_writes_missing_session(tmp_path):
    session_path = tmp_path / "listener.session"
    encoded = base64.b64encode(b"session-bytes").decode("ascii")

    restored = restore_session_from_env(str(session_path), encoded)

    assert restored is True
    assert session_path.read_bytes() == b"session-bytes"


def test_restore_session_from_env_keeps_existing_session(tmp_path):
    session_path = tmp_path / "listener.session"
    session_path.write_bytes(b"existing")
    encoded = base64.b64encode(b"replacement").decode("ascii")

    restored = restore_session_from_env(str(session_path), encoded)

    assert restored is False
    assert session_path.read_bytes() == b"existing"
