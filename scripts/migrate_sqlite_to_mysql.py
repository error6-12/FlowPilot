"""Copy SQLite data to an empty MySQL database, preserving IDs and JSON."""
import argparse
import sys
from pathlib import Path
from sqlalchemy import create_engine, select, func
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config.database import DatabaseConfig
from db.models import Base

def migrate(source_url, target_url=None):
    config = DatabaseConfig(target_url)
    if not source_url.startswith('sqlite:') or not config.connection_string.startswith('mysql'):
        raise ValueError('Source must be SQLite; target must be MySQL')
    source = create_engine(source_url)
    target = create_engine(config.connection_string, **config.get_engine_kwargs())
    try:
        # Validate every row against MySQL column limits before writing anything.
        counts = {}
        with source.connect() as src:
            for table in Base.metadata.sorted_tables:
                counts[table.name] = src.scalar(select(func.count()).select_from(table))
                for row in src.execute(select(table)).mappings():
                    for column in table.columns:
                        limit = getattr(column.type, 'length', None)
                        value = row[column.name]
                        if limit and isinstance(value, str) and len(value) > limit:
                            raise ValueError(f'{table.name}.{column.name} exceeds {limit} characters')
        Base.metadata.create_all(target)
        with source.connect() as src, target.begin() as dst:
            for table in Base.metadata.sorted_tables:
                if dst.scalar(select(func.count()).select_from(table)):
                    raise ValueError('Target contains data; use a new empty database')
            for table in Base.metadata.sorted_tables:
                batch = []
                for row in src.execute(select(table)).mappings():
                    batch.append(dict(row))
                    if len(batch) >= 500:
                        dst.execute(table.insert(), batch)
                        batch = []
                if batch:
                    dst.execute(table.insert(), batch)
                copied = dst.scalar(select(func.count()).select_from(table))
                if copied != counts[table.name]:
                    raise RuntimeError(f'Row count mismatch: {table.name}')
        return counts
    finally:
        source.dispose()
        target.dispose()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', default='sqlite:///data/smart_appointment.db')
    args = parser.parse_args()
    try:
        for name, count in migrate(args.source).items():
            print(f'{name}: {count} rows migrated')
    except Exception as exc:
        # Driver exceptions can contain connection URLs or user data.
        print(f'Migration failed ({type(exc).__name__}). Check credentials, schema and target emptiness.', file=sys.stderr)
        sys.exit(1)
