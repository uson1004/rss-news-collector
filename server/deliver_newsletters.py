from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime
from pathlib import Path

from newsletter_delivery import deliver_due_newsletters

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    load_dotenv = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deliver due newsletter subscriptions.")
    parser.add_argument("--limit", type=int, default=100, help="Maximum due subscriptions to process.")
    parser.add_argument("--dry-run", action="store_true", help="Report due work without sending or mutating state.")
    parser.add_argument("--now", default=None, help="ISO timestamp used for deterministic delivery window selection.")
    return parser.parse_args()


def parse_now(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


async def main() -> int:
    if load_dotenv is not None:
        load_dotenv(Path(__file__).with_name(".env"))
    args = parse_args()
    summary = await deliver_due_newsletters(now=parse_now(args.now), limit=args.limit, dry_run=args.dry_run)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
