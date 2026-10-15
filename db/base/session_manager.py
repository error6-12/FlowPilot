from contextlib import contextmanager
from sqlalchemy import create_engine
from config.database import DatabaseConfig
from sqlalchemy.orm import sessionmaker, scoped_session
from ..models import Base


class SessionManager:
    """
    数据库会话管理器
    
    职责：
    1. 管理数据库连接和会话
    2. 提供统一的会话上下文管理
    3. 处理事务和异常回滚
    """
    
    def __init__(self, db_path=None):
        """
        初始化会话管理器
        
        Args:
            db_path: 数据库连接路径
        """
        config = DatabaseConfig(db_path)
        self.engine = create_engine(config.connection_string, **config.get_engine_kwargs())
        Base.metadata.create_all(self.engine)
        self.Session = scoped_session(sessionmaker(bind=self.engine))

    @contextmanager
    def session_scope(self):
        """
        提供会话上下文管理
        
        自动处理：
        - 会话创建和关闭
        - 事务提交和回滚
        - 异常处理
        """
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            self.Session.remove()

    def close(self):
        """关闭会话管理器"""
        self.Session.remove()
        self.engine.dispose()
