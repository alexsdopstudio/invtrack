"""Command-line entry points:

    python -m app.cli init-db          # create tables (quick start; Alembic for Supabase)
    python -m app.cli ingest all       # or one of: tickers congress insider fundamentals prices
    python -m app.cli score            # recompute composite scores
    python -m app.cli seed-demo        # load synthetic demo data (no network needed)
"""

import argparse
import logging

from .db import Base, SessionLocal, engine as db_engine
from .ingestion.runner import ALL_SOURCES, run_sources
from .scoring import engine as scoring_engine

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def main() -> None:
    parser = argparse.ArgumentParser(prog="invtrack")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init-db")
    ingest = sub.add_parser("ingest")
    ingest.add_argument("source", choices=[*ALL_SOURCES, "all"])
    sub.add_parser("score")
    sub.add_parser("seed-demo")
    args = parser.parse_args()

    if args.command == "init-db":
        Base.metadata.create_all(db_engine)
        print("tables created")
        return

    with SessionLocal() as db:
        if args.command == "ingest":
            sources = ALL_SOURCES if args.source == "all" else [args.source]
            for run in run_sources(db, sources):
                print(f"{run.source}: {run.status} ({run.rows_upserted} rows)"
                      + (f" — {run.error.splitlines()[0]}" if run.error else ""))
            stored = scoring_engine.compute_and_store(db)
            print(f"recomputed {len(stored)} scores")
            from .alerts import detect_alerts

            print(f"{len(detect_alerts(db))} new alerts")
        elif args.command == "score":
            for score in scoring_engine.compute_and_store(db):
                print(f"{score.ticker}: {score.total}")
        elif args.command == "seed-demo":
            from .demo import seed_demo

            Base.metadata.create_all(db_engine)
            for source, count in seed_demo(db).items():
                print(f"{source}: {count} rows")


if __name__ == "__main__":
    main()
