import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import user


def main():
    parser = argparse.ArgumentParser(
        description="Migrate legacy users/*.json profiles into SQLite storage."
    )
    parser.add_argument(
        "--users-dir",
        default="users",
        help="Directory containing legacy JSON user profiles",
    )
    parser.add_argument(
        "--delete-json",
        action="store_true",
        help="Delete JSON files after successful migration",
    )
    args = parser.parse_args()

    result = user.migrate_legacy_json_profiles(
        users_dir=args.users_dir,
        delete_json=args.delete_json,
    )
    print(
        "Migration complete:",
        f"migrated={result['migrated']}",
        f"skipped={result['skipped']}",
        f"deleted={result['deleted']}",
    )


if __name__ == "__main__":
    main()
