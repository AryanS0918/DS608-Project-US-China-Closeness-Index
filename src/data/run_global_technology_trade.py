"""Run restart-safe global technology-trade collection and production processing."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from src.data.collect_technology_trade import collect, find_repository_root


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-year", type=int, default=2004)
    parser.add_argument("--end-year", type=int, default=2024)
    parser.add_argument("--basket", default="include_broad_ict")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--delay", type=float, default=1.1)
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--skip-processing", action="store_true")
    args = parser.parse_args()

    root = find_repository_root()
    result = collect(
        root=root,
        start_year=args.start_year,
        end_year=args.end_year,
        pilot=False,
        basket=args.basket,
        refresh=args.refresh,
        delay=args.delay,
        batch_size=args.batch_size,
        max_retries=args.max_retries,
    )
    print("\nGlobal collection status counts")
    print(result["status"].value_counts(dropna=False).to_string())

    if not args.skip_processing:
        print("\nRunning established technology-trade production builder")
        subprocess.run(
            [sys.executable, "-m", "src.data.build_technology_trade"],
            cwd=root,
            check=True,
        )


if __name__ == "__main__":
    main()
