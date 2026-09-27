"""Copy a stopped local SQLite portfolio database to the shared default path."""

import argparse
import os
from pathlib import Path
import sqlite3
import tempfile

from .config import Settings


def copy_database(source: Path, destination: Path) -> None:
    source = source.expanduser().resolve(strict=True)
    destination = destination.expanduser().resolve()
    if source == destination:
        raise ValueError("Source and destination are the same file.")
    if destination.exists():
        raise FileExistsError(f"Destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".pandaset-copy-", dir=destination.parent)
    os.close(descriptor)
    try:
        with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as original:
            with sqlite3.connect(temporary) as copied:
                original.backup(copied)
                if copied.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                    raise sqlite3.DatabaseError("The copied database failed its integrity check.")
        os.link(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Existing SQLite portfolio database")
    args = parser.parse_args()
    destination = Path.home() / ".pandaset" / "portfolios.sqlite3"
    copy_database(args.source, destination)
    print(f"Copied portfolio database to {destination}. The source was not changed.")


if __name__ == "__main__":
    main()
