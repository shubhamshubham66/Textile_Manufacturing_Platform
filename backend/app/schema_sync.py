"""Add columns that the models have but an existing database is missing.

`create_all` makes missing *tables* but never changes existing ones, so a new
column added to a model (e.g. machines.power_overhead_cost) breaks every query
on a database created before that change ("column ... does not exist").

This runs on startup after `create_all` and only ADDS columns: it never drops,
renames or changes a column, so existing data is untouched. New columns are
added as nullable with the model's default, which fills existing rows.
"""

from __future__ import annotations

import logging

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.sql.schema import Column

log = logging.getLogger(__name__)


def _default_sql(col: Column, engine: Engine) -> str | None:
    d = col.default
    if d is None or not getattr(d, "is_scalar", False):
        return None
    v = d.arg
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, str):
        return "'" + v.replace("'", "''") + "'"
    return None


def add_missing_columns(engine: Engine, metadata) -> list[str]:
    """Return the list of "table.column" names that were added."""
    insp = inspect(engine)
    existing_tables = set(insp.get_table_names())
    added: list[str] = []
    with engine.begin() as conn:
        for table in metadata.sorted_tables:
            if table.name not in existing_tables:
                continue  # create_all already made it with every column
            have = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name in have:
                    continue
                coltype = col.type.compile(dialect=engine.dialect)
                sql = f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {coltype}'
                default = _default_sql(col, engine)
                if default is not None:
                    sql += f" DEFAULT {default}"
                conn.execute(text(sql))
                added.append(f"{table.name}.{col.name}")
    for name in added:
        log.info("Added missing column %s", name)
    return added
