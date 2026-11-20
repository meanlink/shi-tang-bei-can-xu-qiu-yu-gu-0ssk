from sqlalchemy import inspect, text
from src.config.database import Base, engine
from src import models


# 轻量补充迁移：create_all 只建新表，不修改已存在的表；这里补齐新增列。
_ADDED_COLUMNS = {
    'datasets': {'sellout_revision': 'INTEGER DEFAULT 0'},
    'jobs': {'basis': 'JSON', 'run_token': "VARCHAR(64) DEFAULT ''"},
}


def _ensure_columns():
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    dialect = engine.dialect.name
    with engine.begin() as connection:
        for table, columns in _ADDED_COLUMNS.items():
            if table not in existing_tables:
                continue
            present = {column['name'] for column in inspector.get_columns(table)}
            for name, ddl in columns.items():
                if name in present:
                    continue
                statement = f'ALTER TABLE {table} ADD COLUMN {name} {ddl}'
                if dialect == 'mysql':
                    statement = f'ALTER TABLE {table} ADD COLUMN {name} {ddl}'
                connection.execute(text(statement))


def migrate():
    Base.metadata.create_all(engine)
    _ensure_columns()


if __name__ == '__main__':
    migrate()
