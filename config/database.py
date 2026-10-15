"""Shared database configuration. Explicit URLs override environment settings."""
import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy.engine import URL, make_url

class DatabaseConfig:
    def __init__(self, database_url=None):
        load_dotenv(Path(__file__).resolve().parents[1] / '.env')
        self.db_path = database_url or os.getenv('DATABASE_URL') or URL.create(
            'mysql+pymysql',
            username=os.getenv('MYSQL_USER', 'flowpilot'),
            password=os.getenv('MYSQL_PASSWORD', ''),
            host=os.getenv('MYSQL_HOST', '127.0.0.1'),
            port=int(os.getenv('MYSQL_PORT', '3306')),
            database=os.getenv('MYSQL_DATABASE', 'flowpilot'),
            query={'charset': 'utf8mb4'},
        ).render_as_string(hide_password=False)
        self.echo = os.getenv('DB_ECHO', 'false').lower() == 'true'
        self.pool_size = int(os.getenv('DB_POOL_SIZE', '10'))
        self.max_overflow = int(os.getenv('DB_MAX_OVERFLOW', '20'))

    @property
    def connection_string(self):
        return self.db_path

    @property
    def is_sqlite(self):
        return make_url(self.db_path).get_backend_name() == 'sqlite'

    def get_engine_kwargs(self):
        kwargs = {'echo': self.echo}
        if self.is_sqlite:
            kwargs['connect_args'] = {'check_same_thread': False}
        else:
            kwargs.update(pool_size=self.pool_size, max_overflow=self.max_overflow,
                          pool_pre_ping=True, pool_recycle=1800)
        return kwargs

db_config = DatabaseConfig()
