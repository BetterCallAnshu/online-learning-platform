"""Entry point for the Online Learning Platform.

Usage:
    python main.py           start with the existing database
    python main.py --reset   rebuild the database and demo data from scratch
"""

import argparse

import db
import seed
from cli import run


def main():
    parser = argparse.ArgumentParser(description="Online Learning Platform")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="delete the database and reload the demo dataset",
    )
    args = parser.parse_args()

    conn = db.reset() if args.reset else db.connect()
    if not args.reset:
        db.init_schema(conn)

    if seed.seed(conn):
        print("Created the database and loaded the demo dataset.")
        print("Demo accounts are listed in README.md.\n")

    try:
        run(conn)
    except KeyboardInterrupt:
        print("\nGoodbye.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
