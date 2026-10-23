"""Create the schema and (re)generate the fictional demo dataset.

Usage:  python scripts/seed_database.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.seed import seed_database  # noqa: E402
from utils.config import settings  # noqa: E402
from utils.db_connection import get_engine  # noqa: E402

if __name__ == "__main__":
    print(f"Seeding {settings.database_url} ...")
    counts = seed_database(get_engine())
    for table, n in counts.items():
        print(f"  {table:<10} {n:>7,}")
    print("Done.")
