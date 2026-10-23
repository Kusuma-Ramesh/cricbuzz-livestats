"""Export sql/schema.sql, sql/queries.sql and sql/sample_data.sql from the live code and database.

Usage:  python scripts/export_sql.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sqlalchemy.schema import CreateIndex, CreateTable  # noqa: E402

from database import models  # noqa: E402
from utils.db_connection import ensure_database, get_engine  # noqa: E402
from utils.queries import Q  # noqa: E402


def main() -> None:
    engine = get_engine()
    ensure_database()
    out = ROOT / "sql"
    out.mkdir(exist_ok=True)

    parts = ["-- Cricbuzz LiveStats schema (SQLite dialect)\n"]
    for table in models.metadata.sorted_tables:
        parts.append(str(CreateTable(table).compile(engine)).strip() + ";\n")
        for idx in sorted(table.indexes, key=lambda i: i.name):
            parts.append(str(CreateIndex(idx).compile(engine)).strip() + ";\n")
    for name, body in models.VIEWS.items():
        parts.append(f"CREATE VIEW {name} AS {' '.join(body.split())};\n")
    (out / "schema.sql").write_text("\n".join(parts), encoding="utf-8")

    qs = [
        "-- The 25 SQL practice questions. Replace :today, :d30, :d3y with ISO dates "
        "(e.g. '2026-10-19', '2026-09-19', '2023-10-20').\n"
    ]
    for q in Q:
        qs.append(f"-- Q{q.number:02d} [{q.level}] {q.title}\n-- {q.business}\n{q.sql};\n")
    (out / "queries.sql").write_text("\n".join(qs), encoding="utf-8")

    raw = engine.raw_connection()
    try:
        lines = [ln for ln in raw.driver_connection.iterdump() if ln.startswith("INSERT")]
    finally:
        raw.close()
    (out / "sample_data.sql").write_text(
        "-- Fictional demo data\nBEGIN;\n" + "\n".join(lines) + "\nCOMMIT;\n", encoding="utf-8"
    )
    print(f"Wrote schema.sql, queries.sql and sample_data.sql ({len(lines):,} INSERT statements)")


if __name__ == "__main__":
    main()
