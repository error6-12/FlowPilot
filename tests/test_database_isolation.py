from db.base.session_manager import SessionManager


def test_session_manager_uses_temporary_sqlite_database(tmp_path):
    database_file = tmp_path / "agent-test.db"
    manager = SessionManager(f"sqlite:///{database_file.as_posix()}")

    try:
        assert database_file.exists()
        with manager.session_scope() as session:
            assert session.is_active
    finally:
        manager.close()
