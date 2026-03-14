#!/usr/bin/env python
"""
Content Engine CLI — Management Commands

Usage:
    python manage.py seed-content-engine              # Seed all active verticals
    python manage.py seed-content-engine --vertical X  # Seed specific vertical
    python manage.py seed-content-engine --force       # Clear and re-seed
    python manage.py list-verticals                    # Show verticals + config status
"""

import argparse
import sys


def cmd_seed_content_engine(args):
    from app.content_engine.setup_db import seed_content_engine
    seed_content_engine(vertical_name=args.vertical, force=args.force)
    print("Done.")


def cmd_list_verticals(args):
    from app.content_engine.setup_db import list_verticals_status
    results = list_verticals_status()
    if not results:
        print("No verticals found in database.")
        return

    print(f"{'Name':<30} {'Active':<8} {'Preset':<25} {'Weights':<10} {'Seasons':<8}")
    print("-" * 85)
    for r in results:
        print(
            f"{r['name']:<30} "
            f"{'Yes' if r['is_active'] else 'No':<8} "
            f"{r['preset']:<25} "
            f"{'Yes' if r['has_weights'] else 'No':<10} "
            f"{r['season_count']:<8}"
        )


def main():
    parser = argparse.ArgumentParser(description="Content Engine Management CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # seed-content-engine
    seed_parser = subparsers.add_parser("seed-content-engine", help="Seed content engine config")
    seed_parser.add_argument("--vertical", type=str, default=None, help="Seed only this vertical")
    seed_parser.add_argument("--force", action="store_true", help="Clear existing and re-seed")
    seed_parser.set_defaults(func=cmd_seed_content_engine)

    # list-verticals
    list_parser = subparsers.add_parser("list-verticals", help="List verticals and config status")
    list_parser.set_defaults(func=cmd_list_verticals)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
