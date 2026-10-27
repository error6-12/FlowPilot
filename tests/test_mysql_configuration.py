from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateTable
from config.database import DatabaseConfig
from db.models import Base, KnowledgeDocument
from db.base.session_manager import SessionManager
import pytest

def test_all_tables_compile_for_mysql():
    for table in Base.metadata.sorted_tables:
        assert 'CREATE TABLE' in str(CreateTable(table).compile(dialect=mysql.dialect()))

def test_environment_used_by_default(monkeypatch, tmp_path):
    url = f"sqlite:///{(tmp_path / 'configured.db').as_posix()}"
    monkeypatch.setenv('DATABASE_URL', url)
    manager = SessionManager()
    try:
        from sqlalchemy.engine import make_url
        assert manager.engine.url == make_url(url)
        assert (tmp_path / 'configured.db').exists()
    finally:
        manager.close()

def test_mysql_password_special_characters(monkeypatch):
    monkeypatch.setattr('config.database.load_dotenv', lambda *args, **kwargs: None)
    monkeypatch.delenv('DATABASE_URL', raising=False)
    monkeypatch.setenv('MYSQL_PASSWORD', 'a@b:/?#')
    from sqlalchemy.engine import make_url
    assert make_url(DatabaseConfig().connection_string).password == 'a@b:/?#'

def test_transaction_rollback(tmp_path):
    manager = SessionManager(f"sqlite:///{(tmp_path / 'rollback.db').as_posix()}")
    try:
        with pytest.raises(RuntimeError):
            with manager.session_scope() as session:
                session.add(KnowledgeDocument(content='中文知识', category='测试', keywords=['中文']))
                session.flush()
                raise RuntimeError('rollback')
        with manager.session_scope() as session:
            assert session.query(KnowledgeDocument).count() == 0
    finally:
        manager.close()

